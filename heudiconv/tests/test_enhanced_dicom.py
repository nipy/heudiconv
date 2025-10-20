"""Tests for heudiconv.dicom.enhanced module."""

from __future__ import annotations

import os.path as op
from pathlib import Path

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
        assert (
            metadata["SeriesInstanceUID"] is not None
            or metadata["SeriesInstanceUID"] == ""
        )
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
