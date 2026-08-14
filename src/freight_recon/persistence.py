"""The minimum persistence abstraction: one runtime, two supported backends (P5, ADR-016).

    **PostgreSQL is the production transactional store.** SQLite remains for local development
    and deterministic testing only. ### The persistence layer keeps a single schema/migration
    discipline across both. — ADR-016 §1
    P5's capability: durable event execution (outbox/inbox/replay) **ON** production-grade
    persistence.

WHY A WRAPPER AND NOT A REWRITE

`event_outbox`, `event_inbox` and `event_timers` are certified code that already encodes hard-won
semantics: emit refuses outside a transaction, the relay leases whole aggregates, consumption and
the inbox row share one commit. Rewriting them for a second dialect would put every one of those
properties back in play.

So this is a **connection wrapper that presents the sqlite3 API those modules already speak** —
`execute`, `commit`, `rollback`, `in_transaction`, rows addressable by name — and translates
underneath. The runtime changes by a handful of lines; the semantics do not change at all, which is
the only way "the same product semantics hold on both backends" can be a claim rather than a hope.

### THE FOUR REAL DIFFERENCES, AND HOW EACH IS HANDLED

1. **Placeholders.** SQLite `?`, PostgreSQL `%s`. Translated, and translated OUTSIDE string
   literals so a `?` inside a quoted value is never rewritten.

2. **`BEGIN IMMEDIATE` has no PostgreSQL equivalent, and this is the load-bearing one.** SQLite
   takes the write lock at BEGIN, which is what serialises the outbox's `MAX(sequence)+1`
   allocation — the comment in `TransactionalOutbox.emit` says so outright: *"BEGIN IMMEDIATE
   serializes writers, so no second allocator can be between the read and the insert."*
   PostgreSQL's `BEGIN` takes no such lock, so two concurrent emitters would both read the same MAX
   and allocate the same sequence. Under MVCC neither blocks the other and both commit.
   ### **That is a silent duplicate-sequence corruption, not an error**, and it is exactly the
   class of difference this abstraction exists to stop. `begin_immediate()` on PostgreSQL therefore
   takes a **per-tenant advisory transaction lock**, which reproduces SQLite's serialisation for
   the writers that need it and is released automatically at commit or rollback.

3. **Integrity errors.** SQLite raises `sqlite3.IntegrityError` for both a UNIQUE violation and a
   trigger `RAISE(ABORT)`; PostgreSQL raises `UniqueViolation` for one and `RaiseException` for the
   other. The runtime classifies on the message, so both are surfaced as one exception type with
   the message preserved — otherwise a trigger refusal on PostgreSQL would escape the handler that
   turns it into `StrictOrderViolation`.

4. **Rows by name.** `sqlite3.Row` supports `row["col"]`; psycopg's default tuple does not. The
   PostgreSQL cursor uses a dict row factory and results are wrapped so `row["col"]` works
   identically. The runtime reads columns by NAME everywhere precisely because positional access
   silently mis-maps, and that stays true here.

WHAT THIS DOES NOT DO

No pooling, no ORM, no query builder, no schema management (that is `migrations/postgres_p5.py`),
no credential handling — the caller supplies a connection. P6 needs none of those, and P5's
contract asks for none.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

SQLITE = "sqlite"
POSTGRES = "postgres"


class PersistenceError(RuntimeError):
    """The persistence layer cannot do what was asked."""


class IntegrityViolation(Exception):
    """One integrity failure type across both backends.

    ### THE RUNTIME CLASSIFIES ON THE MESSAGE, so the message must survive the crossing. SQLite
    reports a UNIQUE violation and a trigger `RAISE(ABORT)` through one exception type, and
    `event_outbox` distinguishes them by looking for the trigger's abort text. PostgreSQL splits
    them across `UniqueViolation` and `RaiseException`, so both are re-raised as this — with the
    text intact — or a trigger refusal would sail past the handler that turns it into a
    `StrictOrderViolation` and be reported as a duplicate that does not exist.
    """


def _translate(sql: str) -> str:
    """SQLite SQL → PostgreSQL SQL, in ONE literal-aware pass.

    ### ONE SCANNER, NOT TWO. An earlier version was literal-aware for `?` and then handed its
    output to a SEPARATE `MAX(a,b)` rewriter that was not — so `INSERT ... VALUES ('MAX(a, b)')`
    stored `GREATEST(a, b)`. Silent value corruption: precisely the failure this function's own
    docstring calls "the worst kind". The state computed here is now used by every rule.

    Three rules, and each one is a real dialect difference:

      `?`  → `%s`            OUTSIDE string literals only.
      `%`  → `%%`            EVERYWHERE, including inside literals — psycopg parses placeholders
                             before SQL quoting, so a `LIKE 'hel%'` is a hard error otherwise.
      `MAX(a, b)` → `GREATEST(a, b)`   OUTSIDE literals, and ONLY the two-argument form: SQLite's
                             `MAX` is both a one-arg aggregate and a two-arg scalar, PostgreSQL's
                             is only the aggregate. Rewriting the one-arg form would turn a
                             legitimate aggregate into a scalar over one value.
    """
    segments: list[tuple[bool, str]] = []          # (is_literal, text)
    current: list[str] = []
    in_string = False
    quote = ""
    for character in sql:
        if in_string:
            current.append(character)
            if character == quote:
                segments.append((True, "".join(current)))
                current = []
                in_string = False
            continue
        if character in ("'", '"'):
            segments.append((False, "".join(current)))
            current = [character]
            in_string, quote = True, character
            continue
        current.append(character)
    segments.append((in_string, "".join(current)))

    out: list[str] = []
    for is_literal, text in segments:
        if is_literal:
            out.append(text.replace("%", "%%"))
        else:
            # `%` FIRST, then `?`: escaping after substitution would turn the `%s` we just
            # created into `%%s`, and un-doing that would be a rule about our own output.
            out.append(_scalar_max_to_greatest(text).replace("%", "%%").replace("?", "%s"))
    return "".join(out)


def _scalar_max_to_greatest(sql: str) -> str:
    """`MAX(a, b)` → `GREATEST(a, b)`. Two-argument form ONLY. Called on non-literal text only.

    SQLite's `MAX` is BOTH a one-argument aggregate and a two-argument scalar; PostgreSQL's is only
    the aggregate and spells the scalar `GREATEST` — so the inbox's cursor upsert
    (`applied_version = MAX(applied_version, excluded.applied_version)`) is not slower on
    PostgreSQL, it is a syntax error. The one-argument aggregate, which the outbox and the parking
    sequence both use, is valid in both and is left exactly alone.
    """
    out: list[str] = []
    index = 0
    lowered = sql.lower()
    while True:
        found = lowered.find("max(", index)
        if found == -1:
            out.append(sql[index:])
            return "".join(out)
        if found > 0 and (sql[found - 1].isalnum() or sql[found - 1] == "_"):
            out.append(sql[index:found + 4])
            index = found + 4
            continue
        depth, commas, cursor = 0, 0, found + 3
        while cursor < len(sql):
            character = sql[cursor]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    break
            elif character == "," and depth == 1:
                commas += 1
            cursor += 1
        out.append(sql[index:found])
        out.append(("GREATEST" if commas == 1 else sql[found:found + 3]) + sql[found + 3:cursor + 1])
        index = cursor + 1


class _Row:
    """A row addressable BOTH by name and by position — exactly like `sqlite3.Row`.

    ### FAITHFUL EMULATION, NOT AN APPROXIMATION, AND THE RUNTIME PROVED WHY. A dict-only row
    broke `int(conn.execute("SELECT COALESCE(MAX(sequence),0)+1 ...").fetchone()[0])` — the outbox
    reads an aggregate result positionally while reading table rows by name, and `sqlite3.Row`
    supports both. Emulating only half of it would have meant changing certified runtime code to
    suit the shim, which is the wrong direction: the shim exists so the runtime does not change.
    """

    __slots__ = ("_values", "_columns")

    def __init__(self, columns: tuple[str, ...], values: tuple[Any, ...]) -> None:
        self._columns = columns
        self._values = values

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        # `sqlite3.Row` looks columns up CASE-INSENSITIVELY and raises `IndexError` (not KeyError)
        # for a name it does not have. Emulating the access pattern but not these two behaviours
        # would make "faithful emulation" a claim rather than a property.
        folded = str(key).lower()
        for index, column in enumerate(self._columns):
            if column.lower() == folded:
                return self._values[index]
        raise IndexError("No item with that key")

    def keys(self) -> list[str]:
        return list(self._columns)

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"_Row({dict(zip(self._columns, self._values))!r})"


class _Result:
    """A cursor result presenting the sqlite3 surface the runtime uses."""

    def __init__(self, rows: list[Any], rowcount: int, *, is_select: bool = False) -> None:
        self._rows = rows
        # sqlite3 reports -1 after a SELECT; psycopg reports the row count. The runtime reads
        # `rowcount` only after UPDATE/DELETE, but a divergence here is exactly the kind that gets
        # depended on later by accident.
        self.rowcount = -1 if is_select else rowcount

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class PostgresConnection:
    """A psycopg connection wearing the sqlite3 `Connection` API the runtime already speaks.

    Deliberately narrow: it implements exactly what `event_outbox`, `event_inbox` and
    `event_timers` call, and nothing else. A wider shim would be a second database layer to keep
    correct, and this one only has to be correct about the four differences in the module docstring.
    """

    dialect = POSTGRES

    def __init__(self, connection: Any, *, tenant_lock: str | None = None) -> None:
        self._conn = connection
        self._in_transaction = False
        self._tenant_lock = tenant_lock
        self._savepoint_counter = 0
        # Mirrors `sqlite3.Row`, so the runtime's `row_factory is sqlite3.Row` readiness check has
        # an honest answer on this backend too rather than being bypassed.
        self.row_factory = sqlite3.Row

    # --- the sqlite3 surface -------------------------------------------------------------------

    @property
    def in_transaction(self) -> bool:
        """### DERIVED FROM THE DRIVER, NOT FROM A SHADOW FLAG.

        psycopg (autocommit=False) opens a real transaction on the FIRST statement, not on an
        explicit BEGIN. A flag set only by `BEGIN` therefore reported False while a transaction was
        genuinely open — so a later `BEGIN IMMEDIATE` was accepted (SQLite raises), and the advisory
        lock could be taken AFTER writes it was meant to protect had already happened.
        """
        status = getattr(self._conn.info, "transaction_status", None)
        if status is None:                                        # pragma: no cover
            return self._in_transaction
        # psycopg TransactionStatus: 0 IDLE, 1 ACTIVE, 2 INTRANS, 3 INERROR. Under autocommit a
        # read leaves IDLE, exactly as sqlite3 does — so this reports the driver's truth rather
        # than a flag that could disagree with it.
        return int(status) != 0

    def execute(self, sql: str, params: Any = ()) -> _Result:
        statement = sql.strip()
        upper = statement.upper()
        if upper.startswith("BEGIN"):
            self._begin(immediate="IMMEDIATE" in upper)
            return _Result([], 0)
        # ### A SAVEPOINT, BECAUSE POSTGRESQL ABORTS THE WHOLE TRANSACTION ON ANY ERROR AND
        # SQLITE DOES NOT. Every one of `DuplicateEmission`, `StrictOrderViolation` and
        # `DuplicateTimer` is raised from INSIDE the caller's open transaction and documented as
        # catchable — on SQLite the caller then commits the surrounding obligation, and on
        # PostgreSQL the next statement raised `InFailedSqlTransaction`. That is the P5 contract's
        # own `SQLite-vs-PostgreSQL behavioral divergence` hostile case, in the certified runtime.
        # Rolling back to a savepoint makes a classified error recoverable on both backends, so the
        # SAME product semantics hold rather than merely the same API.
        savepoint = None
        if self.in_transaction:
            savepoint = f"sp_{self._savepoint_counter}"
            self._savepoint_counter += 1
            with self._conn.cursor() as cursor:
                cursor.execute(f"SAVEPOINT {savepoint}")
        try:
            with self._conn.cursor() as cursor:
                cursor.execute(_translate(statement), tuple(params))
                if cursor.description is None:
                    result = _Result([], cursor.rowcount)
                else:
                    columns = tuple(d[0] for d in cursor.description)
                    result = _Result([_Row(columns, tuple(r)) for r in cursor.fetchall()],
                                     cursor.rowcount, is_select=True)
            if savepoint is not None:
                with self._conn.cursor() as cursor:
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
            return result
        except Exception as exc:                                  # noqa: BLE001
            if savepoint is not None:
                try:
                    with self._conn.cursor() as cursor:
                        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                except Exception:                                 # noqa: BLE001
                    pass
            raise self._classify(exc) from exc

    def commit(self) -> None:
        self._conn.commit()
        self._in_transaction = False

    def rollback(self) -> None:
        self._conn.rollback()
        self._in_transaction = False

    def close(self) -> None:
        self._conn.close()

    # --- the differences -----------------------------------------------------------------------

    def _begin(self, *, immediate: bool) -> None:
        if self.in_transaction:
            # SQLite raises here too; the runtime relies on it (`DedupInbox.consume` refuses to be
            # called with a transaction already open, because it must OWN the commit boundary).
            raise PersistenceError("cannot start a transaction within a transaction")
        if immediate and self._tenant_lock is None:
            # ### FAIL CLOSED. `BEGIN IMMEDIATE` means "serialise writers"; without a tenant there
            # is nothing to serialise ON, so proceeding would give the caller the transaction they
            # asked for and silently not the exclusion — which is worse than refusing.
            raise PersistenceError(
                "BEGIN IMMEDIATE on a PostgreSQL connection opened without a tenant: the advisory "
                "lock that reproduces SQLite's writer serialisation cannot be taken, and without "
                "it two emitters allocate the same sequence and BOTH commit. Open the connection "
                "with connect_postgres(dsn, tenant=...)."
            )
        with self._conn.cursor() as cursor:
            cursor.execute("BEGIN")
        self._in_transaction = True
        if immediate and self._tenant_lock is not None:
            # ### THE SERIALISATION SQLite GETS FROM `BEGIN IMMEDIATE`, REPRODUCED.
            # Without this, two emitters both read `MAX(sequence)` and allocate the same value;
            # under MVCC neither blocks and both commit, so the corruption is silent. The lock is
            # per-tenant (so tenants never contend with each other) and transaction-scoped, so it
            # is released on commit OR rollback without any unlock call to forget.
            with self._conn.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (self._tenant_lock,))

    @staticmethod
    def _classify(exc: Exception) -> Exception:
        name = type(exc).__name__
        if name in ("UniqueViolation", "RaiseException", "CheckViolation",
                    "IntegrityError", "ForeignKeyViolation", "NotNullViolation"):
            return IntegrityViolation(str(exc))
        return exc


def integrity_errors() -> tuple[type[BaseException], ...]:
    """What an `except` clause must name to catch an integrity failure on EITHER backend."""
    return (sqlite3.IntegrityError, IntegrityViolation)


def dialect_of(conn: Any) -> str:
    return getattr(conn, "dialect", SQLITE)


def connect_postgres(dsn: str, *, tenant: str) -> PostgresConnection:
    """Open a PostgreSQL connection wearing the runtime's expected API.

    ### `tenant` IS REQUIRED, AND IT WAS ONCE OPTIONAL. That default was the entire defect wearing
    a keyword argument: `connect_postgres(dsn)` disarmed the advisory lock silently, and eight
    concurrent emitters on such connections allocated ONE sequence eight times with zero errors —
    the exact corruption this module exists to prevent, reachable through its own public entry
    point. A safety mechanism with an opt-out default is not a safety mechanism.

    It is a parameter rather than sniffed from the SQL because the lock must be taken at BEGIN,
    before the first statement reveals which tenant is being written.
    """
    try:
        import psycopg
    except ModuleNotFoundError as exc:                            # pragma: no cover
        raise PersistenceError(
            "psycopg is required for the PostgreSQL backend; the SQLite backend needs nothing"
        ) from exc
    # The default tuple factory: `_Row` provides the name access, so the cursor need not.
    # ### AUTOCOMMIT, SO THAT TRANSACTIONS ARE **EXPLICIT** — WHICH IS WHAT sqlite3 DOES.
    # `sqlite3` opens an implicit transaction for DML and NOT for a SELECT, so a read leaves
    # `in_transaction` False. psycopg with autocommit=False opens one on the FIRST statement of any
    # kind, so every read left a transaction open indefinitely — pinning a snapshot on a long-lived
    # connection, and then making the next `BEGIN IMMEDIATE` a nested-transaction error.
    #
    # With autocommit=True the wrapper issues BEGIN/COMMIT/ROLLBACK itself, so a read opens
    # nothing and a write is always inside the explicit transaction the runtime already requires:
    # `emit`, `schedule` and `cancel` all refuse outside one, and every relay step opens its own.
    raw = psycopg.connect(dsn, autocommit=True)
    return PostgresConnection(raw, tenant_lock=tenant)
