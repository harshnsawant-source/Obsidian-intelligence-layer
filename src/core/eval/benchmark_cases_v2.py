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
]
