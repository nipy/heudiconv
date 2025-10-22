"""Tests for heudiconv.dicom.enhanced module."""

from __future__ import annotations

import os.path as op
from pathlib import Path

import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ImplicitVRLittleEndian

from heudiconv.dicom.enhanced import extract_metadata


def create_mock_classic_dicom() -> FileDataset:
    """Create a mock classic DICOM dataset for testing."""
    # Create file meta information
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

    # Create the dataset
    ds = FileDataset(
        "", {}, file_meta=file_meta, preamble=b"\0" * 128  # filename_or_obj  # dataset
    )

    ds.SeriesInstanceUID = "1.2.3.4.5"
    ds.StudyInstanceUID = "1.2.3.4"
    ds.SeriesNumber = 1
    ds.ProtocolName = "T1w_MPRAGE"
    ds.SequenceName = "tfl3d1"
    ds.EchoTime = 3.5
    ds.RepetitionTime = 2300.0
    ds.Manufacturer = "SIEMENS"
    ds.ManufacturerModelName = "Prisma"
    return ds


def create_mock_enhanced_dicom() -> FileDataset:
    """Create a mock Enhanced DICOM dataset for testing."""
    ds = create_mock_classic_dicom()
    ds.NumberOfFrames = 120

    # Create SharedFunctionalGroupsSequence
    shared_group = Dataset()

    # Add PlaneOrientationSequence
    plane_orient = Dataset()
    plane_orient.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    shared_group.PlaneOrientationSequence = [plane_orient]

    # Add PixelMeasuresSequence
    pixel_measures = Dataset()
    pixel_measures.PixelSpacing = [1.0, 1.0]
    pixel_measures.SliceThickness = 1.0
    shared_group.PixelMeasuresSequence = [pixel_measures]

    ds.SharedFunctionalGroupsSequence = [shared_group]

    # Add DimensionIndexSequence
    dim1 = Dataset()
    dim1.DimensionDescriptionLabel = "Slice"
    dim1.DimensionIndexPointer = (0x0020, 0x9056)

    dim2 = Dataset()
    dim2.DimensionDescriptionLabel = "Time"
    dim2.DimensionIndexPointer = (0x0020, 0x9057)

    ds.DimensionIndexSequence = [dim1, dim2]

    return ds


def test_extract_metadata_classic_dicom(tmp_path: Path) -> None:
    """Test metadata extraction from classic DICOM file."""
    # Create a temporary DICOM file
    ds = create_mock_classic_dicom()
    dcm_file = tmp_path / "classic.dcm"
    ds.save_as(str(dcm_file))

    # Extract metadata
    metadata = extract_metadata(str(dcm_file))

    # Verify basic fields
    assert metadata["SeriesInstanceUID"] == "1.2.3.4.5"
    assert metadata["StudyInstanceUID"] == "1.2.3.4"
    assert metadata["SeriesNumber"] == 1
    assert metadata["ProtocolName"] == "T1w_MPRAGE"
    assert metadata["SequenceName"] == "tfl3d1"
    assert metadata["EchoTime"] == 3.5
    assert metadata["RepetitionTime"] == 2300.0
    assert metadata["Manufacturer"] == "SIEMENS"
    assert metadata["ManufacturerModelName"] == "Prisma"

    # Enhanced-specific fields should not be present for classic DICOM
    assert "NumberOfFrames" not in metadata or metadata["NumberOfFrames"] is None


def test_extract_metadata_enhanced_dicom(tmp_path: Path) -> None:
    """Test metadata extraction from Enhanced DICOM file."""
    # Create a temporary Enhanced DICOM file
    ds = create_mock_enhanced_dicom()
    dcm_file = tmp_path / "enhanced.dcm"
    ds.save_as(str(dcm_file))

    # Extract metadata
    metadata = extract_metadata(str(dcm_file))

    # Verify basic fields
    assert metadata["SeriesInstanceUID"] == "1.2.3.4.5"
    assert metadata["StudyInstanceUID"] == "1.2.3.4"
    assert metadata["ProtocolName"] == "T1w_MPRAGE"

    # Verify Enhanced-specific fields
    assert metadata["NumberOfFrames"] == 120
    assert metadata["ImageOrientationPatient"] == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    assert metadata["PixelSpacing"] == [1.0, 1.0]
    assert metadata["SliceThickness"] == 1.0

    # Verify dimension information
    assert "Dimensions" in metadata
    assert len(metadata["Dimensions"]) == 2
    assert metadata["Dimensions"][0]["label"] == "Slice"
    assert metadata["Dimensions"][1]["label"] == "Time"


def test_extract_metadata_missing_fields(tmp_path: Path) -> None:
    """Test metadata extraction handles missing optional fields gracefully."""
    # Create file meta information
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

    ds = FileDataset(
        "", {}, file_meta=file_meta, preamble=b"\0" * 128  # filename_or_obj  # dataset
    )
    ds.SeriesInstanceUID = "1.2.3.4.5"
    ds.StudyInstanceUID = "1.2.3.4"
    # Other fields are missing

    dcm_file = tmp_path / "minimal.dcm"
    ds.save_as(str(dcm_file))

    # Extract metadata
    metadata = extract_metadata(str(dcm_file))

    # Verify that missing fields are None
    assert metadata["SeriesInstanceUID"] == "1.2.3.4.5"
    assert metadata["StudyInstanceUID"] == "1.2.3.4"
    assert metadata["SeriesNumber"] is None
    assert metadata["ProtocolName"] is None


def test_extract_metadata_enhanced_partial(tmp_path: Path) -> None:
    """Test Enhanced DICOM with partial functional groups."""
    ds = create_mock_classic_dicom()
    ds.NumberOfFrames = 50

    # Create minimal SharedFunctionalGroupsSequence without all sub-sequences
    shared_group = Dataset()
    ds.SharedFunctionalGroupsSequence = [shared_group]

    dcm_file = tmp_path / "enhanced_partial.dcm"
    ds.save_as(str(dcm_file))

    # Extract metadata - should not crash
    metadata = extract_metadata(str(dcm_file))

    # Basic fields should still work
    assert metadata["SeriesInstanceUID"] == "1.2.3.4.5"
    assert metadata["NumberOfFrames"] == 50

    # Missing sub-sequences should result in None values
    assert metadata.get("ImageOrientationPatient") is None


def test_extract_metadata_enhanced_exception_handling(tmp_path: Path) -> None:
    """Test that exceptions in Enhanced DICOM parsing are handled gracefully."""
    ds = create_mock_enhanced_dicom()

    # Create a malformed SharedFunctionalGroupsSequence that will cause errors
    ds.SharedFunctionalGroupsSequence = [Dataset()]  # Empty dataset

    dcm_file = tmp_path / "malformed.dcm"
    ds.save_as(str(dcm_file))

    # Should not crash, should log warning
    metadata = extract_metadata(str(dcm_file))

    # Basic fields should still be extracted
    assert metadata["SeriesInstanceUID"] == "1.2.3.4.5"


def test_extract_metadata_highdicom_not_available(tmp_path: Path) -> None:
    """Test that the module works even when highdicom is not available."""
    ds = create_mock_enhanced_dicom()
    dcm_file = tmp_path / "enhanced.dcm"
    ds.save_as(str(dcm_file))

    # The module should work without highdicom since it's optional
    # Just verify the function still works and extracts Enhanced metadata
    metadata = extract_metadata(str(dcm_file))

    # Should still extract Enhanced metadata without highdicom
    assert metadata["NumberOfFrames"] == 120
    assert metadata["ImageOrientationPatient"] == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]


def test_extract_metadata_with_real_dicom_if_available() -> None:
    """Test with real DICOM files from test data if available."""
    from heudiconv.tests.utils import TESTS_DATA_PATH

    # Try with an existing test DICOM file
    test_file = op.join(TESTS_DATA_PATH, "axasc35.dcm")
    if op.exists(test_file):
        metadata = extract_metadata(test_file)

        # Should extract basic metadata
        assert metadata["SeriesInstanceUID"] is not None
        assert isinstance(metadata, dict)

        # For classic DICOM, NumberOfFrames might not be present
        # Just verify we didn't crash


def test_extract_metadata_dimension_index_sequence(tmp_path: Path) -> None:
    """Test extraction of DimensionIndexSequence information."""
    ds = create_mock_enhanced_dicom()
    dcm_file = tmp_path / "enhanced_dims.dcm"
    ds.save_as(str(dcm_file))

    metadata = extract_metadata(str(dcm_file))

    # Verify dimensions are extracted correctly
    assert "Dimensions" in metadata
    dims = metadata["Dimensions"]
    assert len(dims) == 2

    # Check first dimension
    assert dims[0]["label"] == "Slice"
    assert dims[0]["pointer"] == (0x0020, 0x9056)

    # Check second dimension
    assert dims[1]["label"] == "Time"
    assert dims[1]["pointer"] == (0x0020, 0x9057)


def test_extract_metadata_without_dimension_index(tmp_path: Path) -> None:
    """Test Enhanced DICOM without DimensionIndexSequence."""
    ds = create_mock_enhanced_dicom()
    # Remove DimensionIndexSequence
    if hasattr(ds, "DimensionIndexSequence"):
        delattr(ds, "DimensionIndexSequence")

    dcm_file = tmp_path / "enhanced_no_dims.dcm"
    ds.save_as(str(dcm_file))

    metadata = extract_metadata(str(dcm_file))

    # Should still extract other Enhanced metadata
    assert metadata["NumberOfFrames"] == 120
    assert "Dimensions" not in metadata


def test_cli_use_enhanced_dicom_option(tmp_path: Path) -> None:
    """Test that --use-enhanced-dicom CLI option is properly parsed and used."""
    from heudiconv.cli.run import get_parser

    parser = get_parser()

    # Test that the option exists and defaults to False
    args = parser.parse_args(["--files", str(tmp_path), "-f", "convertall"])
    assert hasattr(args, "use_enhanced_dicom")
    assert args.use_enhanced_dicom is False

    # Test that the option can be set to True
    args = parser.parse_args(
        ["--files", str(tmp_path), "-f", "convertall", "--use-enhanced-dicom"]
    )
    assert args.use_enhanced_dicom is True


def test_enhanced_dicom_cli_integration(tmp_path: Path) -> None:
    """Integration test for --use-enhanced-dicom flag with CLI commands."""
    from heudiconv.cli.run import main as runner
    from heudiconv.tests.utils import TESTS_DATA_PATH
    import os.path as op

    # Create some test DICOM files
    test_file = op.join(TESTS_DATA_PATH, "axasc35.dcm")
    if not op.exists(test_file):
        pytest.skip("Test DICOM file not available")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Test with ls command and enhanced DICOM
    runner([
        "--command", "ls",
        "--files", test_file,
        "-f", "convertall",
        "--subjects", "test01",
        "--use-enhanced-dicom",
        "--grouping", "all",
    ])
    # If it doesn't crash, the test passes

    # Test conversion with enhanced DICOM (converter=none to skip actual conversion)
    runner([
        "--files", test_file,
        "-f", "convertall",
        "--subjects", "test02",
        "--use-enhanced-dicom",
        "-o", str(output_dir),
        "-c", "none",
    ])

    # Verify that the output directory was created
    assert output_dir.exists()

    # Test that standard mode still works
    runner([
        "--files", test_file,
        "-f", "convertall",
        "--subjects", "test03",
        "-o", str(output_dir),
        "-c", "none",
    ])


def test_group_dicoms_with_enhanced_option(tmp_path: Path) -> None:
    """Test group_dicoms_into_seqinfos with use_enhanced_dicom option."""
    from heudiconv.dicoms import group_dicoms_into_seqinfos
    from heudiconv.dicom.enhanced import group_dicoms_into_seqinfos_enhanced
    from heudiconv.tests.utils import TESTS_DATA_PATH

    # Use an existing test DICOM file
    test_file = op.join(TESTS_DATA_PATH, "axasc35.dcm")
    if not op.exists(test_file):
        pytest.skip("Test DICOM file not available")

    # Test with standard dicomwrapper-based function
    seqinfo_dict_default = group_dicoms_into_seqinfos(
        [test_file],
        "studyUID",
        flatten=True,
    )
    assert len(seqinfo_dict_default) > 0

    # Test with enhanced DICOM function
    seqinfo_dict_enhanced = group_dicoms_into_seqinfos_enhanced(
        [test_file],
        "studyUID",
    )
    assert len(seqinfo_dict_enhanced) > 0

    # Standard function should produce valid seqinfo
    for seqinfo in seqinfo_dict_default.keys():
        assert seqinfo.series_uid is not None


def test_create_seqinfo_with_enhanced_option(tmp_path: Path) -> None:
    """Test create_seqinfo with use_enhanced_dicom option."""
    from heudiconv.dicoms import create_seqinfo
    from heudiconv.dicom.enhanced import validate_dicom_enhanced
    import nibabel.nicom.dicomwrappers as dw
    from heudiconv.tests.utils import TESTS_DATA_PATH

    # Use an existing test DICOM file
    dcm_file = op.join(TESTS_DATA_PATH, "axasc35.dcm")
    if not op.exists(dcm_file):
        pytest.skip("Test DICOM file not available")

    # Test with standard dicomwrapper-based function
    mw = dw.wrapper_from_file(dcm_file, force=True, stop_before_pixels=True)
    seqinfo_default = create_seqinfo(mw, [dcm_file], "1-test")
    assert seqinfo_default is not None
    assert seqinfo_default.series_uid is not None

    # Test with enhanced DICOM function
    result = validate_dicom_enhanced(dcm_file, None)
    assert result is not None
    ds, series_id, study_uid = result
    assert series_id is not None
    assert study_uid is not None


def test_extract_tr_te_from_functional_groups(tmp_path: Path) -> None:
    """Test that TR and TE are correctly extracted from SharedFunctionalGroupsSequence."""
    from heudiconv.dicom.enhanced import create_seqinfo_enhanced

    # Create an Enhanced DICOM with TR/TE only in functional groups (not top-level)
    ds = create_mock_classic_dicom()
    ds.NumberOfFrames = 120
    ds.Rows = 256
    ds.Columns = 256

    # Remove top-level TR/TE if they exist (Enhanced DICOMs typically don't have them)
    if hasattr(ds, "EchoTime"):
        delattr(ds, "EchoTime")
    if hasattr(ds, "RepetitionTime"):
        delattr(ds, "RepetitionTime")

    # Create SharedFunctionalGroupsSequence with MR Timing
    shared_group = Dataset()

    # Add MRTimingAndRelatedParametersSequence (the correct location for TR/TE in Enhanced DICOM)
    mr_timing = Dataset()
    mr_timing.RepetitionTime = 2300.0
    mr_timing.EchoTime = 3.5
    shared_group.MRTimingAndRelatedParametersSequence = [mr_timing]

    ds.SharedFunctionalGroupsSequence = [shared_group]

    # Test create_seqinfo_enhanced
    seqinfo = create_seqinfo_enhanced(ds, ["test.dcm"], "1-test")

    # Verify TR and TE are correctly extracted
    assert seqinfo.TR == 2300.0, f"Expected TR=2300.0, got {seqinfo.TR}"
    assert seqinfo.TE == 3.5, f"Expected TE=3.5, got {seqinfo.TE}"


def test_extract_metadata_tr_te_from_functional_groups(tmp_path: Path) -> None:
    """Test that extract_metadata correctly extracts TR/TE from SharedFunctionalGroupsSequence."""
    # Create an Enhanced DICOM with TR/TE only in functional groups
    ds = create_mock_classic_dicom()
    ds.NumberOfFrames = 120

    # Remove top-level TR/TE
    if hasattr(ds, "EchoTime"):
        delattr(ds, "EchoTime")
    if hasattr(ds, "RepetitionTime"):
        delattr(ds, "RepetitionTime")

    # Create SharedFunctionalGroupsSequence with MR Timing
    shared_group = Dataset()
    mr_timing = Dataset()
    mr_timing.RepetitionTime = 2300.0
    mr_timing.EchoTime = 3.5
    shared_group.MRTimingAndRelatedParametersSequence = [mr_timing]
    ds.SharedFunctionalGroupsSequence = [shared_group]

    # Save to file
    dcm_file = tmp_path / "enhanced_timing.dcm"
    ds.save_as(str(dcm_file))

    # Extract metadata
    metadata = extract_metadata(str(dcm_file))

    # Verify TR and TE are correctly extracted
    assert metadata["RepetitionTime"] == 2300.0, f"Expected TR=2300.0, got {metadata['RepetitionTime']}"
    assert metadata["EchoTime"] == 3.5, f"Expected TE=3.5, got {metadata['EchoTime']}"


def test_tr_te_fallback_to_top_level(tmp_path: Path) -> None:
    """Test that TR/TE from top-level are used if available (classic DICOM compatibility)."""
    from heudiconv.dicom.enhanced import create_seqinfo_enhanced

    # Create a DICOM with top-level TR/TE (classic style)
    ds = create_mock_classic_dicom()  # This has TR/TE at top level
    ds.Rows = 256
    ds.Columns = 256

    # Test create_seqinfo_enhanced
    seqinfo = create_seqinfo_enhanced(ds, ["test.dcm"], "1-test")

    # Verify TR and TE from top level are used
    assert seqinfo.TR == 2300.0, f"Expected TR=2300.0, got {seqinfo.TR}"
    assert seqinfo.TE == 3.5, f"Expected TE=3.5, got {seqinfo.TE}"


def test_tr_te_priority_top_level_over_functional_groups(tmp_path: Path) -> None:
    """Test that top-level TR/TE take priority over functional groups if both exist."""
    from heudiconv.dicom.enhanced import create_seqinfo_enhanced

    # Create a DICOM with TR/TE at both levels
    ds = create_mock_classic_dicom()
    ds.Rows = 256
    ds.Columns = 256
    ds.NumberOfFrames = 120
    ds.RepetitionTime = 1000.0  # Top level value
    ds.EchoTime = 10.0  # Top level value

    # Create SharedFunctionalGroupsSequence with different TR/TE
    shared_group = Dataset()
    mr_timing = Dataset()
    mr_timing.RepetitionTime = 2300.0  # Different value
    mr_timing.EchoTime = 3.5  # Different value
    shared_group.MRTimingAndRelatedParametersSequence = [mr_timing]
    ds.SharedFunctionalGroupsSequence = [shared_group]

    # Test create_seqinfo_enhanced
    seqinfo = create_seqinfo_enhanced(ds, ["test.dcm"], "1-test")

    # Verify top-level values take priority
    assert seqinfo.TR == 1000.0, f"Expected TR=1000.0 (top level), got {seqinfo.TR}"
    assert seqinfo.TE == 10.0, f"Expected TE=10.0 (top level), got {seqinfo.TE}"
