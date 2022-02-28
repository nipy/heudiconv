"""Test functions in heudiconv.bids module.
"""

from heudiconv.bids import (
    maybe_na,
    treat_age,
)
from heudiconv.cli.run import main as runner
from .utils import TESTS_DATA_PATH

from os.path import (
    join as pjoin,
    exists as pexists,
)


def test_maybe_na():
    for na in '', ' ', None, 'n/a', 'N/A', 'NA':
        assert maybe_na(na) == 'n/a'
    for notna in 0, 1, False, True, 'value':
        assert maybe_na(notna) == str(notna)


def test_treat_age():
    assert treat_age(0) == '0'
    assert treat_age('0') == '0'
    assert treat_age('0000') == '0'
    assert treat_age('0000Y') == '0'
    assert treat_age('000.1Y') == '0.1'
    assert treat_age('1M') == '0.08'
    assert treat_age('12M') == '1'
    assert treat_age('0000.1') == '0.1'
    assert treat_age(0000.1) == '0.1'


def test_ME_mag_phase_conversion(tmpdir):
    """ Unit test for the case of multi-echo GRE data with
    magnitude and phase.
    The different echoes should be labeled automatically.
    """
    tmppath = tmpdir.strpath
    subID = 'MEGRE'
    args = (
        "-c dcm2niix -o %s -b -f bids_ME --files %s -s %s"
        % (tmpdir, pjoin(TESTS_DATA_PATH, subID), subID)
    ).split(' ')
    runner(args)

    # Check that the expected files have been extracted.
    # This also checks that the "echo" entity comes before "part":
    for part in ['mag', 'phase']:
        for e in range(1,4):
            for ext in ['nii.gz', 'json']:
                assert pexists(
                    pjoin(tmppath, 'sub-%s', 'anat', 'sub-%s_echo-%s_part-%s_MEGRE.%s')
                    % (subID, subID, e, part, ext)
                )
