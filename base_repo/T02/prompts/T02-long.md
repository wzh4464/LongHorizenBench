# T02: CPython — PEP 634 Structural Pattern Matching

## Requirement — self-contained specification

*Upstream reference (do not fetch):* PEP 634 "Structural Pattern Matching: Specification" (`https://peps.python.org/pep-0634/`). Companion PEPs 635 and 636 motivate and tutorialise the feature, but all implementation-relevant rules are below.

The candidate repository is a CPython checkout immediately before the PEP 634 landing. This task adds the `match` statement, its grammar, AST, compiler, and bytecode-level semantics.

---

## 1. Motivation

Python 3.x historically lacks a multi-way dispatch based on structure. Equivalent logic is written today as long `isinstance` chains or `if`/`elif` ladders with explicit field extraction. PEP 634 adds a `match` statement that:

- Examines a scrutinee against a sequence of patterns,
- Binds names based on the shape matched,
- Optionally guards each arm with a `when` clause (`case p if cond:`),
- Integrates with existing types through new dunder methods (`__match_args__`) and ABCs.

The feature is user-facing syntax, an AST extension, new compiler logic, and new opcodes — all of which this task must implement.

## 2. Surface grammar

```
match_stmt:       "match" subject_expr ':' NEWLINE INDENT case_block+ DEDENT
subject_expr:     named_expression [',' [named_expression [',']]]
case_block:       "case" patterns [guard] ':' block
guard:            "if" named_expression
patterns:         open_sequence_pattern | pattern
pattern:          as_pattern | or_pattern
as_pattern:       or_pattern "as" NAME
or_pattern:       '|'.closed_pattern+
closed_pattern:   literal_pattern | capture_pattern | wildcard_pattern |
                  value_pattern | group_pattern | sequence_pattern |
                  mapping_pattern | class_pattern
```

`match` and `case` are **soft keywords** — they become keywords only in the grammatical position where they are expected. They are ordinary identifiers elsewhere, so existing code using `match = ...` continues to compile.

## 3. Pattern kinds

| Pattern | Syntax | Semantics |
|---|---|---|
| Literal | `1`, `"hi"`, `True`, `None` | `==` comparison (or `is` for singletons). Always consumes the subject. |
| Value | `Color.RED` | Named value (dotted) compared with `==`. |
| Wildcard | `_` | Always matches, never binds. |
| Capture | `name` | Always matches, binds to the subject. Conflicts with `_` and with dotted names. |
| Group | `(p)` | Delegates to inner pattern `p`. |
| Sequence | `[p1, p2, *rest, p3]` | Matches sequences (excluding `str`/`bytes`/`bytearray`). At most one `*rest`. |
| Mapping | `{"a": p1, "b": p2, **rest}` | Matches mappings by key equality. `**rest` captures remaining keys into a new dict. |
| Class | `Point(x=1, y=p2)` | Checks `isinstance(subject, Point)`, then positional/keyword attribute matching. |
| OR | `p1 \| p2` | Tries each alternative; all must bind the same names. |
| AS | `p as name` | Inner match + bind subject to `name` on success. |

`__match_args__` on a class converts positional sub-patterns into keyword sub-patterns (e.g. `Point(1, 2)` equivalent to `Point(x=1, y=2)` if `Point.__match_args__ == ("x", "y")`).

## 4. AST representation

Add the following AST schema entries:

```asdl
stmt_kind = ...
          | Match(expr subject, match_case* cases)

match_case = (pattern pattern, expr? guard, stmt* body)

pattern = MatchValue(expr value)
        | MatchSingleton(constant value)
        | MatchSequence(pattern* patterns)
        | MatchMapping(expr* keys, pattern* patterns, identifier? rest)
        | MatchClass(expr cls, pattern* patterns, identifier* kwd_attrs, pattern* kwd_patterns)
        | MatchStar(identifier? name)
        | MatchAs(pattern? pattern, identifier? name)
        | MatchOr(pattern* patterns)
```

## 5. Bytecode additions

Add to the internal opcode header and wire up in the bytecode compiler and the bytecode interpreter:

| Opcode | Stack effect | Purpose |
|---|---|---|
| `MATCH_MAPPING` | 1 → 2 | Push True if TOS is a mapping, else False (leaves original value in place). |
| `MATCH_SEQUENCE` | 1 → 2 | Push True iff TOS is a non-str/bytes sequence. |
| `MATCH_KEYS` | 2 → 3 | TOS is mapping, TOS-1 is tuple of keys. Push tuple of matched values, or None on miss. |
| `MATCH_CLASS oparg` | 3 → 2 | TOS class, TOS-1 subject, TOS-2 kw names tuple. Push extracted attr tuple, or None on miss. |
| `GET_LEN` | 1 → 2 | Push `len(TOS)`. |
| `COPY_DICT_WITHOUT_KEYS` | 2 → 2 | Copy dict excluding the keys in the following tuple. |
| `ROT_N oparg` | n → n | Rotate N topmost items (used for stack juggling during multi-bind). |

These opcodes replace ad-hoc runtime helpers previously used by the interpreter.

## 3. Semantics summary

1. `match subject:` evaluates `subject` exactly once.
2. `case pattern [if guard]:` evaluates patterns in source order.
3. Each pattern either *matches* (committing its name-bindings) or *fails* (discarding them). On match, the `guard` (if any) is evaluated; if it is falsy, the match is retried as a failure.
4. When a case body runs, the match statement terminates (no fall-through).
5. `_` is always a wildcard (never a binding).
6. Irrefutable patterns (`_`, a bare name, `x if True`) must appear last; earlier irrefutable patterns produce a compile-time warning.

## 3. Parser changes

- The PEG grammar gains `match_stmt`, `case_block`, `patterns`, and every `pattern` alternative.
- The PEG parser emits the corresponding AST nodes.
- Soft-keyword logic: `match` and `case` are only treated as keywords in the leading position of a line inside a `match_stmt`/`case_block`; elsewhere they remain identifiers.

## 4. AST changes

In the AST schema (asdl):

```
stmt = ...
     | Match(expr subject, match_case* cases)

match_case = (pattern pattern, expr? guard, stmt* body)

pattern = MatchValue(expr value)
        | MatchSingleton(constant value)
        | MatchSequence(pattern* patterns)
        | MatchMapping(expr* keys, pattern* patterns, identifier? rest)
        | MatchClass(expr cls, pattern* patterns, identifier* kwd_attrs, pattern* kwd_patterns)
        | MatchStar(identifier? name)
        | MatchAs(pattern? pattern, identifier? name)
        | MatchOr(pattern* patterns)
```

## 5. Compiler changes

The bytecode compiler emits bytecode for each pattern form using the new opcodes. A pattern test runs as a sub-graph: successful match leaves the subject value on the stack for the body; failure falls through to the next `case`. `MATCH_KEYS`, `MATCH_CLASS`, `MATCH_MAPPING`, `MATCH_SEQUENCE`, `GET_LEN`, `COPY_DICT_WITHOUT_KEYS` are new opcodes that implement the structural checks.

## 6. Library / tests

- New tests under the dedicated pattern-matching test module exercising:
  - All pattern kinds (literal, capture, wildcard, value, group, sequence, mapping, class, OR, AS).
  - Pattern errors (unreachable `_`, inconsistent capture, non-terminal `|`).
  - Soft-keyword semantics for `match`/`case` as identifiers.
  - `__match_args__` auto-generation in `dataclasses` and `typing.NamedTuple`.
- The standard library `ast` and `dis` modules need to understand the new AST node kinds and opcodes.

## 7. Implementation Task

The candidate must:

1. Update the PEG grammar and regenerate the parser.
2. Add the `Match`, `match_case`, and pattern AST types and regenerate the AST source output.
3. Implement the new opcodes in the ceval loop.
4. Update the bytecode compiler to emit the right bytecode for each pattern kind, including the jump-on-mismatch logic.
5. Support `__match_args__` on user-defined classes and the built-in ABC registrations for `Sequence` and `Mapping`.
6. Add a pattern-matching test module and confirm related syntax/parser test modules still pass.

## 8. Out of scope

- Exhaustiveness checking (the compiler does not warn on non-exhaustive `match`).
- Pattern compilation to a decision tree (the compiler emits sequential `MATCH_*` opcodes; the peephole pass can optimise later).
- Changes to `dis` and `ast.unparse` beyond rendering the new AST node types.
