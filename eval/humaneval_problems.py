# ── humaneval_problems.py ──────────────────────────────────
# 20 problems drawn from the OpenAI HumanEval benchmark.

PROBLEMS = [
    {
        "id": "HE-001", "difficulty": "easy", "entry_point": "has_close_elements",
        "prompt": 'def has_close_elements(numbers: list, threshold: float) -> bool:\n    """Check if any two elements are closer than threshold.\n    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n    >>> has_close_elements([1.0, 2.8, 3.0], 0.3)\n    True\n    """\n',
        "test": 'assert has_close_elements([1.0,2.0,3.0],0.5)==False\nassert has_close_elements([1.0,2.8,3.0],0.3)==True\nassert has_close_elements([1.0,2.0,3.9,4.0],0.3)==True\nassert has_close_elements([1.0,2.0,3.9,4.0],0.05)==False\n',
    },
    {
        "id": "HE-002", "difficulty": "easy", "entry_point": "truncate_number",
        "prompt": 'def truncate_number(number: float) -> float:\n    """Return only the decimal part of a positive float.\n    >>> truncate_number(3.5)\n    0.5\n    """\n',
        "test": 'assert abs(truncate_number(3.5)-0.5)<1e-6\nassert abs(truncate_number(1.33)-0.33)<1e-6\nassert abs(truncate_number(123.456)-0.456)<1e-6\n',
    },
    {
        "id": "HE-003", "difficulty": "easy", "entry_point": "below_zero",
        "prompt": 'def below_zero(operations: list) -> bool:\n    """Return True if balance goes below zero at any point.\n    >>> below_zero([1,2,3])\n    False\n    >>> below_zero([1,2,-4,5])\n    True\n    """\n',
        "test": 'assert below_zero([1,2,3])==False\nassert below_zero([1,2,-4,5])==True\nassert below_zero([1,2,3,-6])==True\nassert below_zero([])==False\n',
    },
    {
        "id": "HE-004", "difficulty": "easy", "entry_point": "mean_absolute_deviation",
        "prompt": 'def mean_absolute_deviation(numbers: list) -> float:\n    """Return Mean Absolute Deviation around the mean.\n    >>> mean_absolute_deviation([1.0,2.0,3.0,4.0])\n    1.0\n    """\n',
        "test": 'assert abs(mean_absolute_deviation([1.0,2.0,3.0,4.0])-1.0)<1e-6\nassert abs(mean_absolute_deviation([1.0,2.0,3.0,4.0,5.0])-1.2)<1e-6\n',
    },
    {
        "id": "HE-005", "difficulty": "easy", "entry_point": "intersperse",
        "prompt": 'def intersperse(numbers: list, delimeter: int) -> list:\n    """Insert delimeter between every two consecutive elements.\n    >>> intersperse([1,2,3],4)\n    [1,4,2,4,3]\n    """\n',
        "test": 'assert intersperse([],4)==[]\nassert intersperse([1,2,3],4)==[1,4,2,4,3]\nassert intersperse([1,2,3,4],0)==[1,0,2,0,3,0,4]\n',
    },
    {
        "id": "HE-006", "difficulty": "easy", "entry_point": "is_palindrome",
        "prompt": 'def is_palindrome(string: str) -> bool:\n    """Check if given string is a palindrome.\n    >>> is_palindrome("aba")\n    True\n    >>> is_palindrome("zbcd")\n    False\n    """\n',
        "test": 'assert is_palindrome("")==True\nassert is_palindrome("aba")==True\nassert is_palindrome("zbcd")==False\nassert is_palindrome("racecar")==True\nassert is_palindrome("hello")==False\n',
    },
    {
        "id": "HE-007", "difficulty": "easy", "entry_point": "greatest_common_divisor",
        "prompt": 'def greatest_common_divisor(a: int, b: int) -> int:\n    """Return GCD of two integers.\n    >>> greatest_common_divisor(3,5)\n    1\n    >>> greatest_common_divisor(25,15)\n    5\n    """\n',
        "test": 'assert greatest_common_divisor(3,5)==1\nassert greatest_common_divisor(25,15)==5\nassert greatest_common_divisor(100,75)==25\nassert greatest_common_divisor(7,7)==7\n',
    },
    {
        "id": "HE-008", "difficulty": "easy", "entry_point": "all_prefixes",
        "prompt": 'def all_prefixes(string: str) -> list:\n    """Return all prefixes from shortest to longest.\n    >>> all_prefixes("abc")\n    ["a","ab","abc"]\n    """\n',
        "test": 'assert all_prefixes("abc")==["a","ab","abc"]\nassert all_prefixes("")==[]\nassert all_prefixes("a")==["a"]\n',
    },
    {
        "id": "HE-009", "difficulty": "medium", "entry_point": "sum_product",
        "prompt": 'def sum_product(numbers: list) -> tuple:\n    """Return (sum, product) of all integers.\n    >>> sum_product([])\n    (0,1)\n    >>> sum_product([1,2,3,4])\n    (10,24)\n    """\n',
        "test": 'assert sum_product([])==(0,1)\nassert sum_product([1,2,3,4])==(10,24)\nassert sum_product([1,1,1])==(3,1)\n',
    },
    {
        "id": "HE-010", "difficulty": "medium", "entry_point": "rolling_max",
        "prompt": 'def rolling_max(numbers: list) -> list:\n    """Return rolling maximum up to each point.\n    >>> rolling_max([1,2,3,2,3,4,2])\n    [1,2,3,3,3,4,4]\n    """\n',
        "test": 'assert rolling_max([1,2,3,2,3,4,2])==[1,2,3,3,3,4,4]\nassert rolling_max([4,3,2,1])==[4,4,4,4]\nassert rolling_max([])==[]\n',
    },
    {
        "id": "HE-011", "difficulty": "medium", "entry_point": "string_sequence",
        "prompt": 'def string_sequence(n: int) -> str:\n    """Return space-delimited numbers from 0 to n.\n    >>> string_sequence(5)\n    "0 1 2 3 4 5"\n    """\n',
        "test": 'assert string_sequence(0)=="0"\nassert string_sequence(5)=="0 1 2 3 4 5"\nassert string_sequence(1)=="0 1"\n',
    },
    {
        "id": "HE-012", "difficulty": "medium", "entry_point": "count_distinct_characters",
        "prompt": 'def count_distinct_characters(string: str) -> int:\n    """Return count of distinct characters (case-insensitive).\n    >>> count_distinct_characters("xyzXYZ")\n    3\n    """\n',
        "test": 'assert count_distinct_characters("xyzXYZ")==3\nassert count_distinct_characters("Jerry")==4\nassert count_distinct_characters("")==0\n',
    },
    {
        "id": "HE-013", "difficulty": "medium", "entry_point": "filter_by_substring",
        "prompt": 'def filter_by_substring(strings: list, substring: str) -> list:\n    """Filter strings containing the given substring.\n    >>> filter_by_substring(["abc","bacd","cde","array"],"a")\n    ["abc","bacd","array"]\n    """\n',
        "test": 'assert filter_by_substring([],"a")==[]\nassert filter_by_substring(["abc","bacd","cde","array"],"a")==["abc","bacd","array"]\nassert filter_by_substring(["abc","def"],"z")==[]\n',
    },
    {
        "id": "HE-014", "difficulty": "medium", "entry_point": "parse_nested_parens",
        "prompt": 'def parse_nested_parens(paren_string: str) -> list:\n    """Return the deepest nesting level for each group.\n    >>> parse_nested_parens("(()()) ((())) () ((())(()))")\n    [2,3,1,3]\n    """\n',
        "test": 'assert parse_nested_parens("(()()) ((())) () ((())(()))")==[2,3,1,3]\nassert parse_nested_parens("() (()) ((())) (((())))")==[1,2,3,4]\n',
    },
    {
        "id": "HE-015", "difficulty": "medium", "entry_point": "how_many_times",
        "prompt": 'def how_many_times(string: str, substring: str) -> int:\n    """Count occurrences including overlaps.\n    >>> how_many_times("aaaa","aa")\n    3\n    """\n',
        "test": 'assert how_many_times("","a")==0\nassert how_many_times("aaa","a")==3\nassert how_many_times("aaaa","aa")==3\nassert how_many_times("aababab","ab")==3\n',
    },
    {
        "id": "HE-016", "difficulty": "hard", "entry_point": "sort_numbers",
        "prompt": 'def sort_numbers(numbers: str) -> str:\n    """Sort space-delimited number words (zero-nine) smallest to largest.\n    >>> sort_numbers("three one five")\n    "one three five"\n    """\n',
        "test": 'assert sort_numbers("three one five")=="one three five"\nassert sort_numbers("")==""\nassert sort_numbers("nine eight seven")=="seven eight nine"\nassert sort_numbers("zero")=="zero"\n',
    },
    {
        "id": "HE-017", "difficulty": "hard", "entry_point": "find_closest_elements",
        "prompt": 'def find_closest_elements(numbers: list) -> tuple:\n    """Return the two closest values as a sorted tuple.\n    >>> find_closest_elements([1.0,2.0,3.0,4.0,5.0,2.2])\n    (2.0,2.2)\n    """\n',
        "test": 'assert find_closest_elements([1.0,2.0,3.0,4.0,5.0,2.2])==(2.0,2.2)\nassert find_closest_elements([1.1,2.2,3.3])==(1.1,2.2)\n',
    },
    {
        "id": "HE-018", "difficulty": "hard", "entry_point": "rescale_to_unit",
        "prompt": 'def rescale_to_unit(numbers: list) -> list:\n    """Rescale list so min=0.0 and max=1.0.\n    >>> rescale_to_unit([1.0,2.0,3.0,4.0,5.0])\n    [0.0,0.25,0.5,0.75,1.0]\n    """\n',
        "test": 'r=rescale_to_unit([1.0,2.0,3.0,4.0,5.0])\nassert all(abs(a-b)<1e-6 for a,b in zip(r,[0.0,0.25,0.5,0.75,1.0]))\n',
    },
    {
        "id": "HE-019", "difficulty": "hard", "entry_point": "parse_music",
        "prompt": 'def parse_music(music_string: str) -> list:\n    """Parse music notation: o=4 beats, o|=2 beats, .|=1 beat.\n    >>> parse_music("o o| .| o| o| .| .| .| .| o o")\n    [4,2,1,2,2,1,1,1,1,4,4]\n    """\n',
        "test": 'assert parse_music("o o| .| o| o| .| .| .| .| o o")==[4,2,1,2,2,1,1,1,1,4,4]\nassert parse_music("")==[]\nassert parse_music("o")==[4]\nassert parse_music(".|")==[1]\n',
    },
    {
        "id": "HE-020", "difficulty": "hard", "entry_point": "encode_cyclic",
        "prompt": 'def encode_cyclic(s: str) -> str:\n    """Encode a string by cycling groups of 3 characters.\n    Groups of 3 chars are cycled: "abc" -> "bca".\n    Remaining chars stay as-is.\n    >>> encode_cyclic("abc")\n    "bca"\n    >>> encode_cyclic("abcd")\n    "bcad"\n    """\n',
        "test": 'assert encode_cyclic("abc")=="bca"\nassert encode_cyclic("abcd")=="bcad"\nassert encode_cyclic("abcdef")=="bcaef d".replace(" ","")\nassert encode_cyclic("")==""\nassert encode_cyclic("a")=="a"\n'.replace('"bcaef d".replace(" ","")', '"bcaefd"'),
    },
]
