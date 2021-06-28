import io
import re
import sys
import warnings
from typing import List, Union


def _remove_comments(string):
    """Remove comments unless the comment character is the last non-whitespace character
    in a line. (This is often used in macros etc.)
    """
    # first remove all lines which are comments only
    comment_lines = []
    lines = string.split("\n")
    for k, line in enumerate(lines):
        sline = line.strip()
        if len(sline) > 0 and sline[0] == "%":
            comment_lines.append(k)
    string = "\n".join([lines[k] for k in range(len(lines)) if k not in comment_lines])

    # https://stackoverflow.com/a/2319116/353337
    # https://stackoverflow.com/a/24209736/353337
    string = re.sub("[ \t]*(?<!\\\\)%.+\n", "\n", string)
    # same with EOF
    string = re.sub("[ \t]*(?<!\\\\)%.+$", "", string)
    return string


def _remove_trailing_whitespace(string):
    return "\n".join([line.rstrip() for line in string.split("\n")])


def _remove_multiple_spaces(string):
    """Replaces multiple spaces by one, except after a newline."""
    return re.sub("([^\n ])  +", r"\1 ", string)


def _remove_multiple_newlines(string):
    string = re.sub("\n\n\n\n+", "\n\n\n", string)
    return string


def _remove_whitespace_around_brackets(string):
    string = re.sub("{[ \t]+", "{", string)
    string = re.sub("[ \t]+}", "}", string)
    string = re.sub("\\([ \t]+", "(", string)
    string = re.sub("[ \t]+\\)", ")", string)
    string = re.sub("[ \t]+\\\\right\\)", "\\\\right)", string)
    return string


def _replace_dollar_dollar(string):
    """Replace $$...$$ by \\[...\\]."""
    p = re.compile(r"\$\$")
    locations = [m.start() for m in p.finditer(string)]
    assert len(locations) % 2 == 0

    k = 0
    ranges = []
    replacements = []
    while k < len(locations):
        ranges.append((locations[k], locations[k + 1] + 2))
        replacements.append("\\[" + string[locations[k] + 2 : locations[k + 1]] + "\\]")
        k += 2

    return _substitute_string_ranges(string, ranges, replacements)


def _replace_dollar(string):
    """Replace $...$ by \\(...\\). See <https://tex.stackexchange.com/q/510/13262>."""
    # (?<!\\\\) checks there is no backslash before (negative lookbehind)
    # (?:\\\\{2})* matches all even numbers of backslashes
    p = re.compile(r"(?<!\\)(?:\\{2})*\$")
    locations = [m.end() for m in p.finditer(string)]
    assert len(locations) % 2 == 0

    k = 0
    ranges = []
    replacements = []
    while k < len(locations):
        ranges.append((locations[k] - 1, locations[k + 1]))
        replacements.append("\\(" + string[locations[k] : locations[k + 1] - 1] + "\\)")
        k += 2

    return _substitute_string_ranges(string, ranges, replacements)


def _replace_obsolete_text_mods(string):
    string = string.replace("{\\bf ", "\\textbf{")
    string = string.replace("{\\it ", "\\textit{")
    string = string.replace("{\\rm ", "\\textrm{")
    string = string.replace("{\\sc ", "\\textsc{")
    string = string.replace("{\\sf ", "\\textsf{")
    string = string.replace("{\\sl ", "\\textsl{")
    string = string.replace("{\\tt ", "\\texttt{")
    # https://tex.stackexchange.com/a/25914/13262:
    # [\em] May be useful when defining macros. In continuous text \emph{...} should be
    # preferred to \em.
    string = string.replace("{\\em ", "\\emph{")
    return string


def _add_space_after_single_subsuperscript(string):
    string = re.sub(r"([\^])([^{\\])([^_\^\s\$})])", r"\1\2 \3", string)
    return string


def _replace_dots(string):
    string = re.sub(r"\.\.\.", r"\\dots", string)
    string = re.sub(r",\\cdots,", r",\\dots,", string)
    return string


def _replace_punctuation_outside_math(string):
    string = re.sub(r"\.\$", "$.", string)
    string = re.sub(r",\$", "$,", string)
    string = re.sub(r";\$", "$;", string)
    string = re.sub(r"!\$", "$!", string)
    string = re.sub(r"\?\$", "$?", string)
    return string


def _remove_whitespace_before_punctuation(string):
    string = re.sub(r"\s+\.", ".", string)
    string = re.sub(r"\s+,", ",", string)
    string = re.sub(r"\s+;", ";", string)
    string = re.sub(r"\s+!", "!", string)
    string = re.sub(r"\s+\?", "?", string)
    return string


def _add_nbsp_before_reference(string):
    string = re.sub(r"\s+\\ref{", r"~\\ref{", string)
    string = re.sub(r"\s+\\eqref{", r"~\\eqref{", string)
    string = re.sub(r"\s+\\cite", r"~\\cite", string)
    return string


def _replace_double_nbsp(string):
    string = re.sub("~~", r"\\quad ", string)
    return string


def _replace_nbsp_space(string):
    string = re.sub("~ ", " ", string)
    string = re.sub(" ~", " ", string)
    return string


def _substitute_string_ranges(string, ranges, replacements):
    if ranges:
        lst = [string[: ranges[0][0]]]
        for k, replacement in enumerate(replacements[:-1]):
            lst += [replacement, string[ranges[k][1] : ranges[k + 1][0]]]
        lst += [replacements[-1], string[ranges[-1][1] :]]
        string = "".join(lst)
    return string


def _replace_over(string):
    p = re.compile(r"\\over[^a-z]")
    locations = [m.start() for m in p.finditer(string)]

    fracs = []
    ranges = []

    for loc in locations:
        skip = False

        # Starting from loc, search to the left for an open {
        num_open_brackets = 1
        k0 = loc - 1
        while num_open_brackets > 0:
            try:
                char0 = string[k0]
            except IndexError:
                skip = True
                break

            if char0 == "{":
                num_open_brackets -= 1
            elif char0 == "}":
                num_open_brackets += 1
            k0 -= 1

        if skip:
            warning = (
                "Could not convert \\over to \\frac at \n```\n"
                + string[max(0, loc - 20) : loc + 24]
                + "\n```\n"
            )
            warnings.warn(warning)
            continue

        numerator = string[k0 + 2 : loc].strip()

        # Starting from loc+5, search to the right for an open }
        num_open_brackets = 1
        k1 = loc + 5
        while num_open_brackets > 0:
            if string[k1] == "}":
                num_open_brackets -= 1
            elif string[k1] == "{":
                num_open_brackets += 1
            k1 += 1
        denominator = string[loc + 5 : k1 - 1].strip()

        fracs.append((numerator, denominator))
        ranges.append((k0 + 1, k1))

    fracs = [f"\\frac{{{num}}}{{{den}}}" for num, den in fracs]

    return _substitute_string_ranges(string, ranges, fracs)


def _add_linebreak_after_double_backslash(string):
    return re.sub(r"\\\\([^\n])", r"\\\\\n\1", string)


def _add_backslash_for_keywords(string):
    insert = []
    for keyword in ["max", "min", "log", "sin", "cos", "exp"]:
        p = re.compile(fr"[^A-Za-z]{keyword}[^A-Za-z]")
        locations = [m.start() for m in p.finditer(string)]
        for loc in locations:
            if string[loc] != "\\":
                insert.append(loc)

    return _substitute_string_ranges(
        string, [(i + 1, i + 1) for i in insert], len(insert) * ["\\"]
    )


def _add_curly_brackets_around_round_brackets_with_exponent(string):
    p = re.compile(r"\)\^")
    locations = [m.start() for m in p.finditer(string)]

    insert = []
    replacements = []
    for loc in locations:
        # Starting from loc, search to the left for an open (
        num_open_brackets = 1
        k = loc - 1
        while num_open_brackets > 0:
            if string[k] == "(":
                num_open_brackets -= 1
            elif string[k] == ")":
                num_open_brackets += 1
            k -= 1
        k += 1

        if k - 5 >= 0 and string[k - 5 : k] == "\\left":
            insert.append(k - 5)
        else:
            insert.append(k)
        replacements.append("{")

        insert.append(loc + 1)
        replacements.append("}")

    return _substitute_string_ranges(string, [(i, i) for i in insert], replacements)


def _replace_def_by_newcommand(string):
    p = re.compile(r"\\def\\[A-Za-z]+")

    ranges = []
    replacements = []
    for m in p.finditer(string):
        ranges.append((m.start(), m.end()))
        replacements.append(f"\\newcommand{{{string[m.start() + 4 : m.end()]}}}")

    return _substitute_string_ranges(string, ranges, replacements)


def _add_linebreak_around_begin_end(string):
    string = re.sub(r"([^\n ]) *(\\begin{.*?})", r"\1\n\2", string)
    string = re.sub(r"(\\begin{.*?}) *([^\n ])", r"\1\n\2", string)

    string = re.sub(r"([^\n ]) *(\\end{.*?})", r"\1\n\2", string)
    string = re.sub(r"(\\end{.*?}) *([^\n ])", r"\1\n\2", string)

    string = re.sub(r"([^\n ]) *(\\\[)", r"\1\n\2", string)
    string = re.sub(r"(\\\[) *([^\n ])", r"\1\n\2", string)

    string = re.sub(r"([^\n ]) *(\\\])", r"\1\n\2", string)
    string = re.sub(r"(\\\]) *([^\n ])", r"\1\n\2", string)
    return string


def _replace_centerline(string):
    return re.sub(r"\\centerline{", r"{\\centering ", string)


def _replace_eqnarray(string):
    return re.sub("eqnarray", "align", string)


def _put_spec_on_same_line_as_environment(string):
    string = re.sub(r"(\\begin{.*?})\s*(\[.*?\])\n", r"\1\2", string)
    string = re.sub(r"(\\begin{.*?})\s*(\[.*?\])([^\n])", r"\1\2\n\3", string)
    return string


def _put_label_on_same_line_as_environment(string):
    out = re.sub(r"(\\begin{.*?})(\[.*?])?\s+(\\label{.*?})(\n)?", r"\1\2\3\4", string)
    out = re.sub(r"(\\section{.*?})\s+(\\label{.*?})(\n)?", r"\1\2\3", out)
    out = re.sub(r"(\\subsection{.*?})\s+(\\label{.*?})(\n)?", r"\1\2\3", out)
    return out


def _replace_colon_equal_by_coloneqq(string):
    out = re.sub(r":\s*=", r"\\coloneqq ", string)
    out = re.sub(r"=\s*:", r"\\eqqcolon ", out)
    return out


def _remove_space_before_tabular_column_specification(string):
    return re.sub(r"(\\begin{tabular})\s*({.*?})", r"\1\2", string)


def _add_spaces_around_equality_sign(string):
    string = re.sub(r"([^\s&])=", r"\1 =", string)
    string = re.sub(r"([^\s])&=", r"\1 &=", string)

    string = re.sub(r"=([^\s&])", r"= \1", string)
    string = re.sub(r"=&([^\s])", r"=& \1", string)
    return string


def _si_percentage(string):
    # match float like https://stackoverflow.com/a/12643073/353337
    string = re.sub(r"([+-]?([0-9]*[.])?[0-9]+)[ \t]*\\%", r"\\SI{\1}{\%}", string)
    return string


def clean(string, keep_comments=False, keep_dollar=False):
    out = string
    out = _remove_trailing_whitespace(out)
    if not keep_comments:
        out = _remove_comments(out)
    out = _replace_punctuation_outside_math(out)
    out = _replace_dollar_dollar(out)
    if not keep_dollar:
        out = _replace_dollar(out)
    out = _replace_obsolete_text_mods(out)
    out = _remove_whitespace_around_brackets(out)
    out = _add_space_after_single_subsuperscript(out)
    out = _replace_dots(out)
    out = _remove_whitespace_before_punctuation(out)
    out = _add_nbsp_before_reference(out)
    out = _replace_double_nbsp(out)
    out = _replace_nbsp_space(out)
    out = _replace_over(out)
    out = _si_percentage(out)
    out = _add_linebreak_after_double_backslash(out)
    out = _add_backslash_for_keywords(out)
    out = _add_curly_brackets_around_round_brackets_with_exponent(out)
    out = _replace_def_by_newcommand(out)
    out = _add_linebreak_around_begin_end(out)
    out = _replace_centerline(out)
    out = _replace_eqnarray(out)
    out = _put_spec_on_same_line_as_environment(out)
    out = _put_label_on_same_line_as_environment(out)
    out = _replace_colon_equal_by_coloneqq(out)
    out = _remove_space_before_tabular_column_specification(out)
    out = _add_spaces_around_equality_sign(out)
    out = _remove_multiple_newlines(out)
    out = _remove_multiple_spaces(out)
    return out


def process_file(
    infile: Union[io.TextIOWrapper, List[io.TextIOWrapper]],
    outfile: io.TextIOWrapper,
    in_place=False,
    keep_comments=False,
    keep_dollar=False,
    encoding=None,
    *,
    return_values=[],
) -> List[int]:
    if isinstance(infile, list):
        for infile in infile:
            if infile is not sys.stdin and infile is not sys.stdout:
                process_file(infile, outfile, True, keep_comments, keep_dollar)
    else:
        if infile is sys.stdin:
            content = infile.read()
        else:
            with open(infile.name, "r", encoding=encoding) as f:
                content = f.read()

        out = clean(content, keep_comments, keep_dollar)

        if in_place:
            if content != out:
                with open(infile.name, "w", encoding=encoding) as f:
                    f.write(out)
        elif outfile is sys.stdout:
            outfile.write(out)
        else:
            with open(outfile.name, "w", encoding=encoding) as f:
                f.write(out)

        if content != out and (in_place or outfile is not sys.stdout):
            return_values.append(1)
    return return_values
