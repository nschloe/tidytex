# -*- coding: utf-8 -*-
#
import tempfile

import blacktex


def test_cli():
    infile = tempfile.NamedTemporaryFile().name
    with open(infile, 'w') as f:
        f.write("a+b=c")

    outfile = tempfile.NamedTemporaryFile().name

    print(infile, outfile)

    blacktex.cli.main([infile, outfile])

    with open(outfile, 'r') as f:
        line = f.read()
        assert line == "a+b = c"

    return
