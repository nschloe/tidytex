import argparse
import sys

import blacktex


def main(argv=None):
    parser = _get_parser()
    args = parser.parse_args(argv)

    stdout = []
    return_code = 0
    for fl in args.infiles:
        with open(fl.name, encoding=args.encoding) as f:
            content = f.read()
        out = blacktex.clean(content, args.keep_comments, args.keep_dollar_math)
        if args.in_place:
            return_code = return_code or int(content != out)
            with open(fl.name, "w", encoding=args.encoding) as f:
                f.write(out)
        else:
            stdout.append(out)

    if not args.in_place:
        print("\n".join(stdout), end="")

    return return_code


def _get_parser():
    parser = argparse.ArgumentParser(description="Clean up LaTeX files.")

    parser.add_argument(
        "infiles",
        nargs="+",
        type=argparse.FileType("r"),
        help="input LaTeX file",
    )

    parser.add_argument(
        "-e",
        "--encoding",
        type=str,
        default=None,
        help="encoding to use for reading and writing files",
    )

    parser.add_argument(
        "-i", "--in-place", action="store_true", help="modify all files in place"
    )

    parser.add_argument(
        "-c", "--keep-comments", action="store_true", help="keep comments"
    )

    parser.add_argument(
        "-d",
        "--keep-dollar-math",
        action="store_true",
        help="keep inline math with $...$",
    )

    version_text = "blacktex {}, Python {}.{}.{}".format(
        blacktex.__version__,
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    )
    parser.add_argument("--version", "-v", action="version", version=version_text)

    return parser
