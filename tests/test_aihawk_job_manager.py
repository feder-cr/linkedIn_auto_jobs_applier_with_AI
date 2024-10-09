from src.job import Job
from unittest import mock
from pathlib import Path
import os
import pytest
from src.aihawk_job_manager import AIHawkJobManager
from selenium.common.exceptions import NoSuchElementException
from loguru import logger
from src.extractors.extraction_chains import EXTRACTORS


@pytest.fixture
def job_manager(mocker):
    """Fixture to create a AIHawkJobManager instance with mocked driver."""
    mock_driver = mocker.Mock()
    return AIHawkJobManager(mock_driver)


def test_initialization(job_manager):
    """Test AIHawkJobManager initialization."""
    assert job_manager.driver is not None
    assert job_manager.set_old_answers == set()
    assert job_manager.easy_applier_component is None


def test_set_parameters(mocker, job_manager):
    """Test setting parameters for the AIHawkJobManager."""
    # Mocking os.path.exists to return True for the resume path
    mocker.patch('pathlib.Path.exists', return_value=True)

    params = {
        'company_blacklist': ['Company A', 'Company B'],
        'title_blacklist': ['Intern', 'Junior'],
        'positions': ['Software Engineer', 'Data Scientist'],
        'locations': ['New York', 'San Francisco'],
        'apply_once_at_company': True,
        'uploads': {'resume': '/path/to/resume'},  # Resume path provided here
        'outputFileDirectory': '/path/to/output',
        'job_applicants_threshold': {
            'min_applicants': 5,
            'max_applicants': 50
        },
        'remote': False,
        'distance': 50,
        'date': {'all time': True}
    }

    job_manager.set_parameters(params)

    # Normalize paths to handle platform differences (e.g., Windows vs Unix-like systems)
    assert str(job_manager.resume_path) == os.path.normpath('/path/to/resume')
    assert str(job_manager.output_file_directory) == os.path.normpath(
        '/path/to/output')


def next_job_page(self, position, location, job_page):
    logger.debug(f"Navigating to next job page: {position} in {location}, page {job_page}")
    self.driver.get(
        f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}&location={location}&start={job_page * 25}")


def test_get_jobs_from_page_no_jobs(mocker, job_manager):
    """Test get_jobs_from_page when no jobs are found."""
    mocker.patch.object(job_manager.driver, 'find_element',
                        side_effect=NoSuchElementException)

    jobs = job_manager.get_jobs_from_page()
    assert jobs == []


def test_get_jobs_from_page_with_jobs(mocker, job_manager):
    """Test get_jobs_from_page when job elements are found."""
    # Mock the no_jobs_element to behave correctly
    mock_no_jobs_element = mocker.Mock()
    mock_no_jobs_element.text = "No matching jobs found"

    # Mocking the find_element to return the mock no_jobs_element
    mocker.patch.object(job_manager.driver, 'find_element',
                        return_value=mock_no_jobs_element)

    # Mock the page_source
    mocker.patch.object(job_manager.driver, 'page_source',
                        return_value="some page content")

    # Ensure jobs are returned as empty list due to "No matching jobs found"
    jobs = job_manager.get_jobs_from_page()
    assert jobs == []  # No jobs expected due to "No matching jobs found"


def test_apply_jobs_with_no_jobs(mocker, job_manager):
    """Test apply_jobs when no jobs are found."""
    # Mocking find_element to return a mock element that simulates no jobs
    mock_element = mocker.Mock()
    mock_element.text = "No matching jobs found"

    # Mock the driver to simulate the page source
    mocker.patch.object(job_manager.driver, 'page_source', return_value="")

    # Mock the driver to return the mock element when find_element is called
    mocker.patch.object(job_manager.driver, 'find_element',
                        return_value=mock_element)

    # Call apply_jobs and ensure no exceptions are raised
    job_manager.apply_jobs()

    # Ensure it attempted to find the job results list
    assert job_manager.driver.find_element.call_count > 0


def test_apply_jobs_with_jobs(mocker, job_manager):
    """Test apply_jobs when jobs are present."""

    # Mock no_jobs_element to simulate the absence of "No matching jobs found" banner
    no_jobs_element = mocker.Mock()
    no_jobs_element.text = ""  # Empty text means "No matching jobs found" is not present
    mocker.patch.object(job_manager.driver, 'find_element',
                        return_value=no_jobs_element)

    # Mock the page_source to simulate what the page looks like when jobs are present
    mocker.patch.object(job_manager.driver, 'page_source',
                        return_value="some job content")

    # Mock the outer find_elements (scaffold-layout__list-container)
    container_mock = mocker.Mock()

    # Mock the inner find_elements to return job list items
    job_element_mock = mocker.Mock()
    # Simulating two job items
    job_elements_list = [job_element_mock, job_element_mock]

    # Return the container mock, which itself returns the job elements list
    container_mock.find_elements.return_value = job_elements_list
    mocker.patch.object(job_manager.driver, 'find_elements',
                        return_value=[container_mock])

    # Mock the extract_job_information_from_tile method to return sample job info
    for e in EXTRACTORS:
        mocker.patch.object(e, 'extract_job_information_from_tile', return_value=(
            "Title", "Company", "Location", "Apply", "Link"))

    # Mock other methods like is_blacklisted, is_already_applied_to_job, and is_already_applied_to_company
    mocker.patch.object(job_manager, 'is_blacklisted', return_value=False)
    mocker.patch.object(
        job_manager, 'is_already_applied_to_job', return_value=False)
    mocker.patch.object(
        job_manager, 'is_already_applied_to_company', return_value=False)

    # Mock the AIHawkEasyApplier component
    job_manager.easy_applier_component = mocker.Mock()

    # Mock the output_file_directory as a valid Path object
    job_manager.output_file_directory = Path("/mocked/path/to/output")

    # Mock Path.exists() to always return True (so no actual file system interaction is needed)
    mocker.patch.object(Path, 'exists', return_value=True)

    # Mock the open function to prevent actual file writing
    mock_open = mocker.mock_open()
    mocker.patch('builtins.open', mock_open)

    # Run the apply_jobs method
    job_manager.apply_jobs()

    # Assertions
    assert job_manager.driver.find_elements.call_count == 1
    # Called for each job element but only for the first extractor.
    assert EXTRACTORS[0].extract_job_information_from_tile.call_count == 2
    # Called for each job element
    assert job_manager.easy_applier_component.job_apply.call_count == 2
    mock_open.assert_called()  # Ensure that the open function was called
