# Benchmark V2 objective case catalog.
#
# Non-canonical, specification-following tasks (NOT textbook algorithms) chosen
# to resist memorization and create headroom: a single-shot solution tends to
# pass the happy path but miss quiet rules / edge cases.
#
# Each case has:
#   public_tests  - shown in the prompt + used by arm B/C's verify loop
#   hidden_tests  - grading ONLY (disjoint from public; adversarial edges)
#   reference     - a known-correct solution, used ONLY by the test suite to
#                   prove the case is self-consistent (reference scores 1.0).
#
# NOTE: this is a SEED catalog (4 validated cases) proving the end-to-end V2
# pipeline. It must be expanded to ~15-18 candidates (see BENCHMARK_V2_DESIGN.md
# task catalog) BEFORE the gated calibration run that culls to the deciding set.

CASES = [

    {
        "id": "v2_format_file_size",
        "category": "spec-following",
        "signal": "objective",
        "probes": "V",
        "task": (
            "Write a function format_file_size(n) that formats an integer byte "
            "count as a human-readable string using binary units "
            "(B, KB, MB, GB, TB; 1 KB = 1024 B). Rules: use the largest unit for "
            "which the value is >= 1; show NO decimals when the value is a whole "
            "number, otherwise exactly ONE decimal (rounded); return '0 B' for 0; "
            "raise ValueError for negative input; raise TypeError if n is not an "
            "int (note: bool is not a valid int here)."
        ),
        "public_tests": [
            "assert format_file_size(0) == '0 B'",
            "assert format_file_size(512) == '512 B'",
            "assert format_file_size(1024) == '1 KB'",
        ],
        "hidden_tests": [
            "assert format_file_size(1536) == '1.5 KB'",
            "assert format_file_size(1048576) == '1 MB'",
            "assert format_file_size(1500000) == '1.4 MB'",
            "assert format_file_size(1023) == '1023 B'",
            "assert format_file_size(1099511627776) == '1 TB'",
            "assert format_file_size(2560) == '2.5 KB'",
            "try:\n    format_file_size(-1)\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    format_file_size(True)\n    assert False\nexcept TypeError:\n    pass",
        ],
        "reference": '''
def format_file_size(n):
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("expected int")
    if n < 0:
        raise ValueError("negative")
    units = ["B", "KB", "MB", "GB", "TB"]
    if n == 0:
        return "0 B"
    v = float(n)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    if i == 0:
        return "%d %s" % (int(v), units[0])
    r = round(v, 1)
    if r == int(r):
        return "%d %s" % (int(r), units[i])
    return "%.1f %s" % (r, units[i])
''',
    },

    {
        "id": "v2_slugify",
        "category": "spec-following",
        "signal": "objective",
        "probes": "V",
        "task": (
            "Write a function slugify(title, stopwords=(), maxlen=50). Lowercase "
            "the title, split on runs of non-alphanumeric ASCII characters into "
            "tokens (drop empties), remove any token that exactly matches a "
            "stopword (case-insensitive), then join the remaining tokens with '-'. "
            "Do NOT transliterate accented characters (treat them as separators). "
            "If the slug would exceed maxlen, include only as many whole tokens as "
            "fit; if even the first token is longer than maxlen, hard-truncate that "
            "token to maxlen characters. Return '' if nothing remains."
        ),
        "public_tests": [
            "assert slugify('Hello World') == 'hello-world'",
            "assert slugify('The Quick Brown Fox', ['the']) == 'quick-brown-fox'",
            "assert slugify('A  B') == 'a-b'",
        ],
        "hidden_tests": [
            "assert slugify('Hello, World!') == 'hello-world'",
            "assert slugify('The cat and the hat', ['the', 'and']) == 'cat-hat'",
            "assert slugify('one two three', (), 7) == 'one-two'",
            "assert slugify('verylongword', (), 5) == 'veryl'",
            "assert slugify('  ') == ''",
            "assert slugify('Caf\\u00e9 M\\u00fcnch\\u00ebn') == 'caf-m-nch-n'",
        ],
        "reference": '''
import re as _re
def slugify(title, stopwords=(), maxlen=50):
    sw = set(w.lower() for w in stopwords)
    tokens = [t for t in _re.split(r"[^a-z0-9]+", str(title).lower()) if t]
    tokens = [t for t in tokens if t not in sw]
    result = []
    length = 0
    for t in tokens:
        add = len(t) if not result else len(t) + 1
        if length + add > maxlen:
            break
        result.append(t)
        length += add
    if not result:
        return tokens[0][:maxlen] if tokens else ""
    return "-".join(result)
''',
    },

    {
        "id": "v2_expand_ranges",
        "category": "spec-following",
        "signal": "objective",
        "probes": "V",
        "task": (
            "Write a function expand_ranges(s) that parses a comma-separated list "
            "of integers and integer ranges like '1-3,5,7-7' and returns a sorted "
            "list of the unique integers covered. A range 'a-b' includes both "
            "endpoints and requires a <= b. Whitespace around items and numbers is "
            "allowed. Overlapping ranges are merged via the set of covered "
            "integers. Raise ValueError on any malformed item (empty item, "
            "non-integer, or a range with start > end)."
        ),
        "public_tests": [
            "assert expand_ranges('1-3') == [1, 2, 3]",
            "assert expand_ranges('5') == [5]",
            "assert expand_ranges('1-3,5') == [1, 2, 3, 5]",
        ],
        "hidden_tests": [
            "assert expand_ranges('7-7') == [7]",
            "assert expand_ranges('3,1,2') == [1, 2, 3]",
            "assert expand_ranges('1-3,2-4') == [1, 2, 3, 4]",
            "assert expand_ranges('10-12,1') == [1, 10, 11, 12]",
            "assert expand_ranges(' 1 - 3 ') == [1, 2, 3]",
            "try:\n    expand_ranges('5-3')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    expand_ranges('a')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    expand_ranges('1,,2')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": '''
def expand_ranges(s):
    out = set()
    for part in str(s).split(","):
        part = part.strip()
        if not part:
            raise ValueError("empty item")
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if a > b:
                raise ValueError("start > end")
            out.update(range(a, b + 1))
        else:
            out.add(int(part))
    return sorted(out)
''',
    },

    {
        "id": "v2_tokenize_template",
        "category": "compositional",
        "signal": "objective",
        "probes": "D",
        "task": (
            "Write a function tokenize_template(template, ctx) that renders a "
            "string template. A placeholder is written {key} and is replaced by "
            "str(ctx[key]). A placeholder may include a filter: {key|filter} where "
            "filter is one of upper, lower, title (applied to the string value). "
            "Surrounding whitespace inside the braces is ignored. Raise KeyError if "
            "a referenced key is missing from ctx; raise ValueError for an unknown "
            "filter. Text outside braces is passed through unchanged."
        ),
        "public_tests": [
            "assert tokenize_template('Hi {name}', {'name': 'bob'}) == 'Hi bob'",
            "assert tokenize_template('{x|upper}', {'x': 'ab'}) == 'AB'",
            "assert tokenize_template('{n} msgs', {'n': 3}) == '3 msgs'",
        ],
        "hidden_tests": [
            "assert tokenize_template('{name|title}', {'name': 'bob smith'}) == 'Bob Smith'",
            "assert tokenize_template('{a} {b}', {'a': 1, 'b': 2}) == '1 2'",
            "assert tokenize_template('no braces', {}) == 'no braces'",
            "assert tokenize_template('{x|lower}', {'x': 'AB'}) == 'ab'",
            "assert tokenize_template('{ x }', {'x': 'ok'}) == 'ok'",
            "try:\n    tokenize_template('{y}', {'x': 1})\n    assert False\nexcept KeyError:\n    pass",
            "try:\n    tokenize_template('{x|reverse}', {'x': 'a'})\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": '''
import re as _re
def tokenize_template(template, ctx):
    filters = {"upper": str.upper, "lower": str.lower, "title": str.title}
    def repl(m):
        body = m.group(1)
        if "|" in body:
            key, f = body.split("|", 1)
            key, f = key.strip(), f.strip()
            if key not in ctx:
                raise KeyError(key)
            if f not in filters:
                raise ValueError(f)
            return filters[f](str(ctx[key]))
        key = body.strip()
        if key not in ctx:
            raise KeyError(key)
        return str(ctx[key])
    return _re.sub(r"\\{([^}]*)\\}", repl, template)
''',
    },

    # ===== expanded candidates (validated by test_benchmark_v2) =====

    {
        "id": "v2_parse_duration",
        "category": "spec-following",
        "signal": "objective",
        "probes": "mixed",
        "task": (
            "Write parse_duration(s) that parses a compact duration like '1h30m' "
            "into total seconds. Allowed units: d=86400, h=3600, m=60, s=1, each "
            "written as <integer><unit> with no spaces, concatenated in any order. "
            "Sum the parts. Raise ValueError if the string is empty, contains any "
            "junk outside <int><unit> tokens, or repeats a unit."
        ),
        "public_tests": [
            "assert parse_duration('1h30m') == 5400",
            "assert parse_duration('45s') == 45",
            "assert parse_duration('2d') == 172800",
        ],
        "hidden_tests": [
            "assert parse_duration('1h') == 3600",
            "assert parse_duration('1h1m1s') == 3661",
            "assert parse_duration('90m') == 5400",
            "try:\n    parse_duration('')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    parse_duration('1x')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    parse_duration('1h1h')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    parse_duration('abc')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
import re as _re
def parse_duration(s):
    s = str(s).strip()
    if not s:
        raise ValueError("empty")
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    matches = list(_re.finditer(r"(\d+)([dhms])", s))
    if not matches or "".join(m.group(0) for m in matches) != s:
        raise ValueError("invalid")
    seen = set()
    total = 0
    for m in matches:
        u = m.group(2)
        if u in seen:
            raise ValueError("dup unit")
        seen.add(u)
        total += int(m.group(1)) * units[u]
    return total
''',
    },

    {
        "id": "v2_validate_brackets",
        "category": "spec-following",
        "signal": "objective",
        "probes": "V",
        "task": (
            "Write validate_brackets(s, pairs) where pairs maps each opening "
            "bracket char to its closing char (e.g. {'(' : ')'}). Return True iff "
            "the brackets in s (only those in pairs) are balanced and correctly "
            "nested; ignore any other characters."
        ),
        "public_tests": [
            "assert validate_brackets('()', {'(': ')'}) == True",
            "assert validate_brackets('(]', {'(': ')', '[': ']'}) == False",
            "assert validate_brackets('ab(c)d', {'(': ')'}) == True",
        ],
        "hidden_tests": [
            "assert validate_brackets('([])', {'(': ')', '[': ']'}) == True",
            "assert validate_brackets('([)]', {'(': ')', '[': ']'}) == False",
            "assert validate_brackets('', {'(': ')'}) == True",
            "assert validate_brackets('(', {'(': ')'}) == False",
            "assert validate_brackets(')(', {'(': ')'}) == False",
            "assert validate_brackets('{a}', {'{': '}'}) == True",
            "assert validate_brackets('no brackets', {'(': ')'}) == True",
        ],
        "reference": r'''
def validate_brackets(s, pairs):
    openers = dict(pairs)
    closers = {c: o for o, c in pairs.items()}
    stack = []
    for ch in s:
        if ch in openers:
            stack.append(ch)
        elif ch in closers:
            if not stack or openers[stack.pop()] != ch:
                return False
    return not stack
''',
    },

    {
        "id": "v2_custom_numeral",
        "category": "spec-following",
        "signal": "objective",
        "probes": "V",
        "task": (
            "Write to_int(s, table) that converts a Roman-style numeral string to "
            "an integer using the symbol->value mapping `table` (NOT standard Roman "
            "values). Apply the subtractive rule: scanning right-to-left, if a "
            "symbol's value is less than the value of the symbol to its right, "
            "subtract it; otherwise add it. Empty string is 0. Raise ValueError on "
            "a symbol not in table."
        ),
        "public_tests": [
            "assert to_int('A', {'A': 1, 'B': 5}) == 1",
            "assert to_int('AB', {'A': 1, 'B': 5}) == 4",
            "assert to_int('BA', {'A': 1, 'B': 5}) == 6",
        ],
        "hidden_tests": [
            "T = {'A': 1, 'B': 5, 'C': 10, 'D': 50}",
            "assert to_int('AC', {'A': 1, 'C': 10}) == 9",
            "assert to_int('CA', {'A': 1, 'C': 10}) == 11",
            "assert to_int('DCCC', {'C': 10, 'D': 50}) == 80",
            "assert to_int('AD', {'A': 1, 'D': 50}) == 49",
            "assert to_int('', {'A': 1}) == 0",
            "try:\n    to_int('X', {'A': 1})\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
def to_int(s, table):
    total = 0
    prev = 0
    for ch in reversed(s):
        if ch not in table:
            raise ValueError(ch)
        v = table[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total
''',
    },

    {
        "id": "v2_normalize_whitespace",
        "category": "spec-following",
        "signal": "objective",
        "probes": "mixed",
        "task": (
            "Write normalize_whitespace(s, mode='single'). mode='single': collapse "
            "every run of whitespace to a single space and strip ends. mode='none': "
            "remove all whitespace. mode='lines': strip each line, drop blank lines, "
            "join remaining lines with '\\n'. Raise ValueError for any other mode."
        ),
        "public_tests": [
            "assert normalize_whitespace('a  b') == 'a b'",
            "assert normalize_whitespace('a b', 'none') == 'ab'",
            "assert normalize_whitespace('  x  ') == 'x'",
        ],
        "hidden_tests": [
            "assert normalize_whitespace('a\\t\\nb') == 'a b'",
            "assert normalize_whitespace('a b c', 'none') == 'abc'",
            "assert normalize_whitespace(' line1 \\n\\n line2 ', 'lines') == 'line1\\nline2'",
            "assert normalize_whitespace('', 'single') == ''",
            "try:\n    normalize_whitespace('x', 'bad')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
import re as _re
def normalize_whitespace(s, mode="single"):
    if mode == "single":
        return _re.sub(r"\s+", " ", s).strip()
    if mode == "none":
        return _re.sub(r"\s+", "", s)
    if mode == "lines":
        lines = [ln.strip() for ln in s.split("\n")]
        return "\n".join(ln for ln in lines if ln)
    raise ValueError("bad mode")
''',
    },

    {
        "id": "v2_calc",
        "category": "compositional",
        "signal": "objective",
        "probes": "D",
        "task": (
            "Write calc(expr) that evaluates an integer arithmetic expression with "
            "+, -, * and parentheses, standard precedence (* before + and -), "
            "left-associative. Whitespace is ignored. No division, no unary minus. "
            "Raise ValueError on any malformed expression."
        ),
        "public_tests": [
            "assert calc('1+2') == 3",
            "assert calc('2*3+1') == 7",
            "assert calc('2*(3+1)') == 8",
        ],
        "hidden_tests": [
            "assert calc('1+2*3') == 7",
            "assert calc('(1+2)*3') == 9",
            "assert calc('10-2-3') == 5",
            "assert calc('2*3*4') == 24",
            "assert calc('((1))') == 1",
            "try:\n    calc('1+')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    calc('')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
import re as _re
def calc(expr):
    s = expr.replace(" ", "")
    tokens = _re.findall(r"\d+|[+\-*()]", s)
    if "".join(tokens) != s:
        raise ValueError("bad chars")
    pos = [0]
    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None
    def nxt():
        t = peek()
        pos[0] += 1
        return t
    def parse_factor():
        t = peek()
        if t == "(":
            nxt()
            v = parse_expr()
            if nxt() != ")":
                raise ValueError("paren")
            return v
        if t is None or not t.isdigit():
            raise ValueError("num")
        nxt()
        return int(t)
    def parse_term():
        v = parse_factor()
        while peek() == "*":
            nxt()
            v = v * parse_factor()
        return v
    def parse_expr():
        v = parse_term()
        while peek() in ("+", "-"):
            op = nxt()
            r = parse_term()
            v = v + r if op == "+" else v - r
        return v
    v = parse_expr()
    if pos[0] != len(tokens):
        raise ValueError("trailing")
    return v
''',
    },

    {
        "id": "v2_eval_postfix",
        "category": "compositional",
        "signal": "objective",
        "probes": "D",
        "task": (
            "Write eval_postfix(expr): evaluate a space-separated reverse-Polish "
            "(postfix) integer expression with operators +, -, *. Operands are "
            "integers (may be negative). Raise ValueError if an operator has too "
            "few operands, a token is neither an integer nor a known operator, or "
            "the expression does not reduce to exactly one value."
        ),
        "public_tests": [
            "assert eval_postfix('1 2 +') == 3",
            "assert eval_postfix('3 4 *') == 12",
            "assert eval_postfix('5 1 2 + *') == 15",
        ],
        "hidden_tests": [
            "assert eval_postfix('1 2 3 + +') == 6",
            "assert eval_postfix('10 2 -') == 8",
            "assert eval_postfix('2 3 4 * +') == 14",
            "assert eval_postfix('-5 3 +') == -2",
            "try:\n    eval_postfix('1 +')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    eval_postfix('1 2')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    eval_postfix('1 a +')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
def eval_postfix(expr):
    stack = []
    for tok in str(expr).split():
        if tok in ("+", "-", "*"):
            if len(stack) < 2:
                raise ValueError("operands")
            b = stack.pop()
            a = stack.pop()
            stack.append(a + b if tok == "+" else a - b if tok == "-" else a * b)
        else:
            try:
                stack.append(int(tok))
            except ValueError:
                raise ValueError("token " + tok)
    if len(stack) != 1:
        raise ValueError("malformed")
    return stack[0]
''',
    },

    {
        "id": "v2_parse_kv",
        "category": "compositional",
        "signal": "objective",
        "probes": "D",
        "task": (
            "Write parse_kv(s) for a small config grammar. Input is newline-"
            "separated lines. Ignore blank lines and lines whose first non-space "
            "char is '#'. Each remaining line is key=value (split on the FIRST '='); "
            "strip whitespace around key and value. If the value is wrapped in "
            "double quotes, remove them (a quoted value may contain '='). Duplicate "
            "keys: last one wins. Raise ValueError on a non-comment line with no '='."
        ),
        "public_tests": [
            "assert parse_kv('a=1') == {'a': '1'}",
            "assert parse_kv('a=1\\nb=2') == {'a': '1', 'b': '2'}",
            "assert parse_kv('# c\\na=1') == {'a': '1'}",
        ],
        "hidden_tests": [
            "assert parse_kv('a = 1 ') == {'a': '1'}",
            "assert parse_kv('a=\"x=y\"') == {'a': 'x=y'}",
            "assert parse_kv('a=1\\na=2') == {'a': '2'}",
            "assert parse_kv('\\n\\na=1\\n') == {'a': '1'}",
            "assert parse_kv('  # comment') == {}",
            "try:\n    parse_kv('novalue')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
def parse_kv(s):
    out = {}
    for line in str(s).split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError("no =")
        k, v = stripped.split("=", 1)
        k = k.strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        out[k] = v
    return out
''',
    },

    {
        "id": "v2_merge_dicts",
        "category": "compositional",
        "signal": "objective",
        "probes": "D",
        "task": (
            "Write merge_dicts(base, override, list_strategy='replace') that deep-"
            "merges override into base and returns a NEW dict (do not mutate "
            "inputs). For keys present in both: if both values are dicts, merge "
            "recursively; if both are lists and list_strategy=='append', "
            "concatenate base then override; otherwise the override value wins. "
            "Raise ValueError if list_strategy is not 'replace' or 'append'."
        ),
        "public_tests": [
            "assert merge_dicts({'a': 1}, {'b': 2}) == {'a': 1, 'b': 2}",
            "assert merge_dicts({'a': 1}, {'a': 2}) == {'a': 2}",
            "assert merge_dicts({'a': {'x': 1}}, {'a': {'y': 2}}) == {'a': {'x': 1, 'y': 2}}",
        ],
        "hidden_tests": [
            "assert merge_dicts({'l': [1]}, {'l': [2]}) == {'l': [2]}",
            "assert merge_dicts({'l': [1]}, {'l': [2]}, 'append') == {'l': [1, 2]}",
            "assert merge_dicts({}, {'a': 1}) == {'a': 1}",
            "assert merge_dicts({'a': {'x': 1}}, {'a': 5}) == {'a': 5}",
            "b = {'a': 1}\nmerge_dicts(b, {'a': 2})\nassert b == {'a': 1}",
            "try:\n    merge_dicts({}, {}, 'bad')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
def merge_dicts(base, override, list_strategy="replace"):
    if list_strategy not in ("replace", "append"):
        raise ValueError("strategy")
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge_dicts(out[k], v, list_strategy)
        elif (k in out and isinstance(out[k], list) and isinstance(v, list)
              and list_strategy == "append"):
            out[k] = out[k] + v
        else:
            out[k] = v
    return out
''',
    },

    {
        "id": "v2_csv_row_parse",
        "category": "compositional",
        "signal": "objective",
        "probes": "D",
        "task": (
            "Write csv_row_parse(line) that parses ONE CSV line into a list of "
            "field strings. Fields are comma-separated. A field may be wrapped in "
            "double quotes, in which case it may contain commas; a doubled quote "
            "(\"\") inside a quoted field is a literal quote. Raise ValueError on an "
            "unterminated quoted field. An empty line yields ['']."
        ),
        "public_tests": [
            "assert csv_row_parse('a,b,c') == ['a', 'b', 'c']",
            "assert csv_row_parse('\"a,b\",c') == ['a,b', 'c']",
            "assert csv_row_parse('a') == ['a']",
        ],
        "hidden_tests": [
            "assert csv_row_parse('') == ['']",
            "assert csv_row_parse('\"a\"\"b\"') == ['a\"b']",
            "assert csv_row_parse('x,,y') == ['x', '', 'y']",
            "assert csv_row_parse('\"hello, world\",2') == ['hello, world', '2']",
            "assert csv_row_parse('a,b,') == ['a', 'b', '']",
            "try:\n    csv_row_parse('\"unterminated')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
def csv_row_parse(line):
    fields = []
    cur = []
    in_q = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if in_q:
            if ch == '"':
                if i + 1 < n and line[i + 1] == '"':
                    cur.append('"')
                    i += 2
                    continue
                in_q = False
                i += 1
                continue
            cur.append(ch)
            i += 1
        else:
            if ch == '"':
                in_q = True
                i += 1
            elif ch == ",":
                fields.append("".join(cur))
                cur = []
                i += 1
            else:
                cur.append(ch)
                i += 1
    if in_q:
        raise ValueError("unterminated")
    fields.append("".join(cur))
    return fields
''',
    },

    {
        "id": "v2_format_phone",
        "category": "spec-following",
        "signal": "objective",
        "probes": "mixed",
        "task": (
            "Write format_phone(digits, fmt) that fills the 'X' placeholders in fmt "
            "with the characters of `digits` in order; all non-'X' characters in "
            "fmt are copied literally. Raise ValueError if `digits` contains a "
            "non-digit, or if the number of digits does not equal the number of 'X' "
            "in fmt."
        ),
        "public_tests": [
            "assert format_phone('1234567890', '(XXX) XXX-XXXX') == '(123) 456-7890'",
            "assert format_phone('12', 'X-X') == '1-2'",
            "assert format_phone('99', 'XX') == '99'",
        ],
        "hidden_tests": [
            "assert format_phone('5', 'X') == '5'",
            "assert format_phone('123', 'X.X.X') == '1.2.3'",
            "assert format_phone('', '') == ''",
            "assert format_phone('12', 'XYX') == '1Y2'",
            "try:\n    format_phone('123', 'XX')\n    assert False\nexcept ValueError:\n    pass",
            "try:\n    format_phone('1a', 'XX')\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
def format_phone(digits, fmt):
    d = list(str(digits))
    if not all(c.isdigit() for c in d):
        raise ValueError("non-digit")
    if len(d) != fmt.count("X"):
        raise ValueError("count")
    it = iter(d)
    out = []
    for ch in fmt:
        out.append(next(it) if ch == "X" else ch)
    return "".join(out)
''',
    },

    {
        "id": "v2_running_total",
        "category": "spec-following",
        "signal": "objective",
        "probes": "V",
        "task": (
            "Write running_total(nums, reset_on=None) that returns the list of "
            "running sums. After appending the running sum for an element, if that "
            "element equals reset_on (and reset_on is not None), reset the "
            "accumulator to 0 for subsequent elements."
        ),
        "public_tests": [
            "assert running_total([1, 2, 3]) == [1, 3, 6]",
            "assert running_total([1, 2, 3], reset_on=2) == [1, 3, 3]",
            "assert running_total([]) == []",
        ],
        "hidden_tests": [
            "assert running_total([5, 5, 5], 5) == [5, 5, 5]",
            "assert running_total([1, 1, 1]) == [1, 2, 3]",
            "assert running_total([0]) == [0]",
            "assert running_total([2, 2], 2) == [2, 2]",
            "assert running_total([-1, 1]) == [-1, 0]",
            "assert running_total([10], 10) == [10]",
        ],
        "reference": r'''
def running_total(nums, reset_on=None):
    acc = 0
    out = []
    for x in nums:
        acc += x
        out.append(acc)
        if reset_on is not None and x == reset_on:
            acc = 0
    return out
''',
    },

    {
        "id": "v2_chunk",
        "category": "spec-following",
        "signal": "objective",
        "probes": "mixed",
        "task": (
            "Write chunk(seq, size, pad=None) that splits seq into consecutive "
            "lists of length `size`. If pad is not None, pad the final short chunk "
            "with `pad` up to `size`; if pad is None, leave the final chunk short. "
            "Raise ValueError if size < 1. Always return a list of lists."
        ),
        "public_tests": [
            "assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]",
            "assert chunk([1, 2, 3], 2) == [[1, 2], [3]]",
            "assert chunk([1, 2, 3], 2, pad=0) == [[1, 2], [3, 0]]",
        ],
        "hidden_tests": [
            "assert chunk([], 3) == []",
            "assert chunk([1, 2, 3, 4, 5], 2, pad=9) == [[1, 2], [3, 4], [5, 9]]",
            "assert chunk('abc', 1) == [['a'], ['b'], ['c']]",
            "assert chunk([1], 5, pad=0) == [[1, 0, 0, 0, 0]]",
            "assert chunk([1, 2], 2, pad=0) == [[1, 2]]",
            "try:\n    chunk([1], 0)\n    assert False\nexcept ValueError:\n    pass",
        ],
        "reference": r'''
def chunk(seq, size, pad=None):
    if size < 1:
        raise ValueError("size")
    seq = list(seq)
    out = []
    for i in range(0, len(seq), size):
        c = seq[i:i + size]
        if pad is not None and len(c) < size:
            c = c + [pad] * (size - len(c))
        out.append(c)
    return out
''',
    },

    {
        "id": "v2_titlecase",
        "category": "spec-following",
        "signal": "objective",
        "probes": "mixed",
        "task": (
            "Write titlecase(s, small_words=()) that capitalizes the first letter "
            "of each space-separated word and lowercases the rest, EXCEPT words in "
            "small_words are kept fully lowercase — unless the word is the first or "
            "last word, which is always capitalized. Preserve single spaces."
        ),
        "public_tests": [
            "assert titlecase('the lord of the rings', ['of', 'the']) == 'The Lord of the Rings'",
            "assert titlecase('a tale', ['a']) == 'A Tale'",
            "assert titlecase('hello world') == 'Hello World'",
        ],
        "hidden_tests": [
            "assert titlecase('welcome to the jungle', ['to', 'the']) == 'Welcome to the Jungle'",
            "assert titlecase('of mice and men', ['of', 'and']) == 'Of Mice and Men'",
            "assert titlecase('x', ['x']) == 'X'",
            "assert titlecase('the the the', ['the']) == 'The the The'",
            "assert titlecase('hello WORLD') == 'Hello World'",
        ],
        "reference": r'''
def titlecase(s, small_words=()):
    sw = set(w.lower() for w in small_words)
    words = s.split(" ")
    n = len(words)
    out = []
    for i, w in enumerate(words):
        if not w:
            out.append(w)
            continue
        lw = w.lower()
        if lw in sw and i != 0 and i != n - 1:
            out.append(lw)
        else:
            out.append(lw[0].upper() + lw[1:])
    return " ".join(out)
''',
    },

    {
        "id": "v2_interval_overlap",
        "category": "spec-following",
        "signal": "objective",
        "probes": "V",
        "task": (
            "Write interval_overlap(a, b) where a and b are [start, end] inclusive "
            "integer intervals (start <= end). Return their overlap as [s, e], or "
            "None if they do not overlap. Intervals that touch at a single point "
            "DO overlap (the overlap is that point)."
        ),
        "public_tests": [
            "assert interval_overlap([1, 5], [3, 7]) == [3, 5]",
            "assert interval_overlap([1, 2], [3, 4]) is None",
            "assert interval_overlap([1, 5], [2, 3]) == [2, 3]",
        ],
        "hidden_tests": [
            "assert interval_overlap([1, 3], [3, 5]) == [3, 3]",
            "assert interval_overlap([1, 1], [1, 1]) == [1, 1]",
            "assert interval_overlap([5, 10], [1, 4]) is None",
            "assert interval_overlap([0, 10], [2, 8]) == [2, 8]",
            "assert interval_overlap([-5, 0], [-2, 3]) == [-2, 0]",
            "assert interval_overlap([1, 5], [5, 5]) == [5, 5]",
        ],
        "reference": r'''
def interval_overlap(a, b):
    s = max(a[0], b[0])
    e = min(a[1], b[1])
    if s > e:
        return None
    return [s, e]
''',
    },
]
