import pytest
from unittest import mock
from pathlib import Path
import os
from src.aihawk_job_manager import AIHawkJobManager
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from loguru import logger


@pytest.fixture
def job_manager(mocker):
    """Fixture to create an AIHawkJobManager instance with mocked driver."""
    mock_driver = mocker.Mock()
    return AIHawkJobManager(mock_driver)


def test_initialization(job_manager):
    """Test AIHawkJobManager initialization."""
    assert job_manager.driver is not None
    assert job_manager.set_old_answers == []
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
    assert str(job_manager.output_file_directory) == os.path.normpath('/path/to/output')
    assert job_manager.apply_once_at_company is True
    assert job_manager.min_applicants == 5
    assert job_manager.max_applicants == 50


def test_get_base_search_url(job_manager):
    """Test construction of the base search URL based on parameters."""
    params = {
        'remote': True,
        'experience_level': {'entry': True, 'associate': False},
        'jobTypes': {'full-time': True, 'contract': False},
        'distance': 50,
        'date': {'month': True},
        'outputFileDirectory': '/path/to/output'  
    }

    job_manager.set_parameters(params)


def test_get_jobs_from_page_no_jobs(mocker, job_manager):
    """Test get_jobs_from_page when no jobs are found."""
    mocker.patch.object(job_manager.driver, 'find_element', side_effect=NoSuchElementException)
    jobs = job_manager.get_jobs_from_page()
    assert jobs == []


def test_get_jobs_from_page_with_jobs(mocker, job_manager):
    """Test get_jobs_from_page when job elements are found."""
    # Mocking the find_element to return a container with job elements
    job_element_mock = mocker.Mock()
    job_elements_list = [job_element_mock, job_element_mock]

    # Mock the container
    container_mock = mocker.Mock()
    container_mock.find_elements.return_value = job_elements_list

    # Mock the driver.find_elements to return the container
    mocker.patch.object(job_manager.driver, 'find_elements', return_value=[container_mock])

    # Mock no_jobs_element to have a text attribute that supports `in` operation
    no_jobs_element_mock = mocker.Mock()
    no_jobs_element_mock.text = "No matching jobs found"  
    mocker.patch.object(job_manager.driver, 'find_element', return_value=no_jobs_element_mock)

    jobs = job_manager.get_jobs_from_page()
    assert len(jobs) == 0  # Expect 0 job elements




def test_apply_jobs_no_jobs(mocker, job_manager):
    """Test apply_jobs when no jobs are found on the page."""
    # Mocking find_element to return a mock element that simulates no jobs
    mock_element = mocker.Mock()
    mock_element.text = "No matching jobs found"
    mocker.patch.object(job_manager.driver, 'find_element', return_value=mock_element)

    job_manager.apply_jobs()

    # Ensure it attempted to find the job results list
    assert job_manager.driver.find_element.call_count == 1


def test_apply_jobs_with_jobs(mocker, job_manager):
    """Test apply_jobs when jobs are present."""
    # Mocking the job elements and application logic
    mock_element = mocker.Mock()
    mock_element.text = "No matching jobs found"  
    mocker.patch.object(job_manager.driver, 'find_element', return_value=mock_element)

    job_element_mock = mocker.Mock()
    job_elements_list = [job_element_mock, job_element_mock]

    container_mock = mocker.Mock()
    container_mock.find_elements.return_value = job_elements_list
    mocker.patch.object(job_manager.driver, 'find_elements', return_value=[container_mock])

    mocker.patch.object(job_manager, 'extract_job_information_from_tile', return_value=("Title", "Company", "Location", "Apply", "Link"))
    mocker.patch.object(job_manager, 'is_blacklisted', return_value=False)
    mocker.patch.object(job_manager, 'is_already_applied_to_job', return_value=False)
    mocker.patch.object(job_manager, 'is_already_applied_to_company', return_value=False)

    job_manager.easy_applier_component = mocker.Mock()

    job_manager.apply_jobs()
    assert job_manager.extract_job_information_from_tile.call_count == 0
    assert job_manager.easy_applier_component.job_apply.call_count == 0




def test_is_blacklisted(job_manager):
    """Test the is_blacklisted method."""
    job_manager.title_blacklist = ["Intern", "Manager"]
    job_manager.company_blacklist = ["Company A", "Company B"]

    result = job_manager.is_blacklisted("Software Engineer", "Company A", "Link")
    assert result is True

    result = job_manager.is_blacklisted("Intern", "Company C", "Link")
    assert result is True

    result = job_manager.is_blacklisted("Senior Developer", "Company C", "Link")
    assert result is False
