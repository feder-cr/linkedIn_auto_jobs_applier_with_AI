from unittest import mock

import pytest
from loguru import logger
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement

from src.aihawk_easy_applier import AIHawkEasyApplier


@pytest.fixture
def mock_driver():
    """Fixture to mock Selenium WebDriver."""
    return mock.Mock()


@pytest.fixture
def mock_gpt_answerer():
    """Fixture to mock GPT Answerer."""
    return mock.Mock()


@pytest.fixture
def mock_resume_generator_manager():
    """Fixture to mock Resume Generator Manager."""
    return mock.Mock()


@pytest.fixture
def mock_job():
    """Fixture to create a mock job object."""
    return mock.Mock()


@pytest.fixture
def easy_applier(mock_driver, mock_gpt_answerer, mock_resume_generator_manager, mock_job):
    """Fixture to initialize AIHawkEasyApplier with mocks."""
    return AIHawkEasyApplier(
        driver=mock_driver,
        resume_dir="/path/to/resume",
        set_old_answers=[('Question 1', 'Answer 1', 'Type 1')],
        gpt_answerer=mock_gpt_answerer,
        resume_generator_manager=mock_resume_generator_manager,
        job_application_profile=mock_job
    )


def test_initialization(mocker, easy_applier):
    """Test that AIHawkEasyApplier is initialized correctly."""
    mocker.patch('os.path.exists', return_value=True)

    easy_applier = AIHawkEasyApplier(
        driver=mocker.Mock(),
        resume_dir="/path/to/resume",
        set_old_answers=[('Question 1', 'Answer 1', 'Type 1')],
        gpt_answerer=mocker.Mock(),
        resume_generator_manager=mocker.Mock(),
        job_application_profile=mocker.Mock()
    )

    assert easy_applier.resume_path == "/path/to/resume"
    assert len(easy_applier.set_old_answers) == 1
    assert easy_applier.gpt_answerer is not None
    assert easy_applier.resume_generator_manager is not None
    assert easy_applier.job_application_profile is not None


def test_apply_to_job_success(mocker, easy_applier, mock_job):
    """Test successfully applying to a job."""
    mocker.patch.object(easy_applier, 'job_apply')

    easy_applier.apply_to_job(mock_job)
    easy_applier.job_apply.assert_called_once_with(mock_job)


def test_apply_to_job_failure(mocker, easy_applier, mock_job):
    """Test failure while applying to a job."""
    mocker.patch.object(easy_applier, 'job_apply', side_effect=Exception("Test error"))

    with pytest.raises(Exception, match="Test error"):
        easy_applier.apply_to_job(mock_job)

    easy_applier.job_apply.assert_called_once_with(mock_job)


def test_check_for_premium_redirect_no_redirect(easy_applier, mock_job):
    """Test that check_for_premium_redirect works when there's no redirect."""
    easy_applier.driver.current_url = "https://www.linkedin.com/jobs/view/1234"

    easy_applier.check_for_premium_redirect(mock_job)
    easy_applier.driver.get.assert_not_called()


def test_check_for_premium_redirect_with_redirect(mocker, easy_applier, mock_job):
    """Test that check_for_premium_redirect handles LinkedIn Premium redirects."""
    easy_applier.driver.current_url = "https://www.linkedin.com/premium"
    mock_job.link = "https://www.linkedin.com/jobs/view/1234"

    with pytest.raises(Exception, match="Redirected to LinkedIn Premium page and failed to return"):
        easy_applier.check_for_premium_redirect(mock_job)

    assert easy_applier.driver.get.call_count == 3


def test_fill_application_form_success(mocker, easy_applier, mock_job):
    """Test successfully filling and submitting the application form."""
    mocker.patch.object(easy_applier, 'fill_up')
    mocker.patch.object(easy_applier, '_next_or_submit', return_value=True)

    easy_applier._fill_application_form(mock_job)
    easy_applier.fill_up.assert_called_once_with(mock_job)
    easy_applier._next_or_submit.assert_called_once()


def test_fill_application_form_failure(mocker, easy_applier, mock_job):
    """Test failing to fill the application form and check logs."""
    log_messages = []

    logger.remove()
    logger.add(log_messages.append)

    mocker.patch.object(easy_applier, 'fill_up')
    mocker.patch.object(easy_applier, '_next_or_submit', side_effect=Exception("Form error"))

    try:
        easy_applier._fill_application_form(mock_job)
    except Exception:
        pass 

    assert any("Form filling failed: Form error" in message for message in log_messages), (
        f"Expected log message not found in logs: {log_messages}"
    )


def test_get_job_description_success(mocker, easy_applier):
    """Test successfully retrieving the job description."""
    mock_description_element = mock.Mock(spec=WebElement)
    mock_description_element.text = "Job description text"
    mocker.patch.object(easy_applier.driver, 'find_element', return_value=mock_description_element)

    description = easy_applier._get_job_description()
    assert description == "Job description text"


def test_get_job_description_failure(mocker, easy_applier):
    """Test failing to retrieve the job description."""
    mocker.patch.object(easy_applier.driver, 'find_element', side_effect=NoSuchElementException)

    with pytest.raises(Exception, match="Job description not found"):
        easy_applier._get_job_description()


def test_create_and_upload_resume_file_too_large(mocker, easy_applier, mock_job):
    """Test creating and uploading a resume when the file size is too large."""
    mock_element = mocker.Mock(spec=WebElement)
    mocker.patch('os.makedirs', return_value=None)
    mocker.patch('builtins.open', mock.mock_open())
    mocker.patch('os.path.isfile', return_value=True)
    mocker.patch('os.path.getsize', return_value=3 * 1024 * 1024)
    mocker.patch.object(easy_applier.resume_generator_manager, 'pdf_base64', return_value=b"")

    with pytest.raises(ValueError, match="Resume file size exceeds the maximum limit of 2 MB"):
        easy_applier._create_and_upload_resume(mock_element, mock_job)
