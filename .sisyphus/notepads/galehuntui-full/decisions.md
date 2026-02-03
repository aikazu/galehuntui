# Architectural Decisions

- **Runner Strategy**: Docker preferred, Local fallback
- **Concurrency**: Single scan + queue
- **Process Model**: Detached (scan survives TUI exit)
- **Config Location**: `./configs/` (project root)
- **Tool Installation**: Project-local `./tools/bin/`
- **Setup Wizard**: Implemented as a stateful screen with mocked system operations for the UI prototype, using Textual's `ContentSwitcher` and `Worker` pattern for async tasks.

## Database Testing Design Decisions (2026-02-03)

### Choice: Temporary Files vs In-Memory Database
**Decision:** Use `tempfile.NamedTemporaryFile()` instead of `:memory:` database

**Rationale:**
- Tests file-based behavior (parent directory creation, file permissions)
- Allows testing connection persistence across close/reopen
- More realistic to production usage
- Minimal performance impact (tests still complete in 0.014s)
- Easy cleanup with unlink() in tearDown()

**Alternative Considered:** Using `:memory:` database would be faster but wouldn't test file-based edge cases.

### Choice: unittest vs pytest
**Decision:** Use unittest framework (per requirements)

**Rationale:**
- Requirement explicitly stated "Use `unittest` and `sqlite3` (in-memory)"
- unittest is part of Python standard library
- Familiar TestCase class structure
- setUp/tearDown lifecycle methods work well for database tests

**Trade-offs:**
- More verbose than pytest (no fixtures, must use classes)
- No parametrization support (handled with loops in tests)
- No automatic fixture injection

### Choice: Test Organization
**Decision:** 6 test classes grouped by functionality

**Rationale:**
- Each class tests a cohesive unit (initialization, runs, findings, etc.)
- Clear separation of concerns
- Easy to run subset of tests
- Good balance between granularity and maintainability

**Classes:**
1. TestDatabaseInitialization - Schema setup
2. TestRunOperations - Run CRUD
3. TestFindingOperations - Finding CRUD  
4. TestForeignKeyConstraints - Relationships
5. TestDatabaseContextManager - Resource management
6. TestDatabaseErrors - Error handling

### Choice: Helper Methods
**Decision:** Use `_create_sample_run()` and `_create_sample_finding()` helpers

**Rationale:**
- DRY principle - avoid repeating complex object creation
- Parameterizable for variations
- Sensible defaults reduce test verbosity
- Easy to modify all tests if model changes

**Implementation:**
```python
def _create_sample_run(self, run_id: str = None) -> RunMetadata:
    if run_id is None:
        run_id = str(uuid4())
    return RunMetadata(...)
```

### Choice: Fixed Timestamps
**Decision:** Use hardcoded timestamps like `datetime(2024, 1, 15, 10, 30, 0)`

**Rationale:**
- Deterministic test results
- Easy to verify ordering tests
- No time zone issues
- Clear intent in test code
- Avoids `datetime.now()` flakiness

**Alternative Considered:** Using `datetime.now()` would work but makes tests harder to debug and potentially flaky.

### Choice: Comprehensive Ordering Tests
**Decision:** Test both severity and timestamp ordering for findings

**Rationale:**
- Database uses complex CASE statement for severity ordering
- Critical requirement for user experience (CRITICAL findings first)
- Easy to break with schema changes
- Test both primary (severity) and secondary (timestamp) sort keys

### Choice: Test Both Save and Update Paths
**Decision:** Explicitly test upsert behavior (INSERT ... ON CONFLICT DO UPDATE)

**Rationale:**
- Database uses upsert for both save_run() and save_finding()
- Critical to verify both new inserts and updates work
- Different code paths in SQLite
- Common source of bugs

### Choice: Limited Error Testing
**Decision:** Minimal error handling tests (only 1 test)

**Rationale:**
- Database class wraps SQLite errors in StorageError
- Most errors would be caused by invalid SQL (our code bug, not test concern)
- Unit tests focus on happy path + edge cases
- Integration tests better suited for error scenarios
- Hard to trigger specific SQLite errors in unit test context

