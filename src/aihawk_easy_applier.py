import base64
import json
import os
import random
import re
import time
import traceback
from typing import List, Optional, Any, Tuple

from httpx import HTTPStatusError
from loguru import logger
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import src.utils as utils
from loguru import logger


class AIHawkEasyApplier:
    def __init__(self, driver, resume_dir, set_old_answers, gpt_answerer, resume_generator_manager, job_application_profile):
        logger.debug("Initializing AIHawkEasyApplier")
        self.driver = driver
        self.resume_path = resume_dir
        self.set_old_answers = set_old_answers
        self.gpt_answerer = gpt_answerer
        self.resume_generator_manager = resume_generator_manager
        self.job_application_profile = job_application_profile  # Store the job_application_profile
        self.all_data = self._load_questions_from_json()
        logger.debug("AIHawkEasyApplier initialized successfully")

    def _load_questions_from_json(self) -> List[dict]:
        """Load previously stored questions and answers from a JSON file."""
        output_file = 'answers.json'
        logger.debug(f"Loading questions from JSON file: {output_file}")
        try:
            with open(output_file, 'r') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("JSON file format is incorrect. Expected a list of questions.")
                except json.JSONDecodeError:
                    logger.error("JSON decoding failed")
                    data = []
            logger.debug("Questions loaded successfully from JSON")
            return data
        except FileNotFoundError:
            logger.warning("JSON file not found, returning empty list")
            return []
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error loading questions data from JSON file: {tb_str}")
            raise Exception(f"Error loading questions data from JSON file: \nTraceback:\n{tb_str}")

    def check_for_premium_redirect(self, job: Any, max_attempts=3):
        """
        Checks if the current page redirects to a LinkedIn Premium page and attempts to navigate back to the job page.
        Args:
            job (Any): The job object containing the job link.
            max_attempts (int): Maximum number of attempts to try navigating back.
        """
        current_url = self.driver.current_url
        attempts = 0

        while "linkedin.com/premium" in current_url and attempts < max_attempts:
            logger.warning("Redirected to LinkedIn Premium page. Attempting to return to the job page.")
            attempts += 1
            self.driver.get(job.link)
            time.sleep(2)
            current_url = self.driver.current_url

        if "linkedin.com/premium" in current_url:
            logger.error(f"Failed to return to the job page after {max_attempts} attempts. Cannot apply for the job.")
            raise Exception(
                f"Redirected to LinkedIn Premium page and failed to return after {max_attempts} attempts. Job application aborted.")

    def apply_to_job(self, job: Any) -> None:
        """
        Starts the process of applying to a job.
        Args:
            job (Any): A job object with the job details.
        """
        logger.debug(f"Applying to job: {job}")
        try:
            self.job_apply(job)
            logger.info(f"Successfully applied to job: {job.title}")
        except Exception as e:
            logger.error(f"Failed to apply to job: {job.title}, error: {str(e)}")
            raise e

    def job_apply(self, job: Any):
        """
        Main function to apply for a LinkedIn job using the Easy Apply feature.
        Args:
            job (Any): The job object containing details like job link, company, and position.
        """
        logger.debug(f"Starting job application for job: {job}")

        try:
            self.driver.get(job.link)
            logger.debug(f"Navigated to job link: {job.link}")
        except Exception as e:
            logger.error(f"Failed to navigate to job link: {job.link}, error: {str(e)}")
            raise

        time.sleep(random.uniform(3, 5))
        self.check_for_premium_redirect(job)

        try:
            if self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Application submitted')]"):
                logger.info(f"Job application already submitted for job: {job}. Skipping.")
                return
            else:
                logger.debug("No indication of prior application found. Proceeding with application.")
        except Exception as e:
            logger.error(f"Error while checking for application status: {e}")
            raise

        try:
            self.driver.execute_script("document.activeElement.blur();")
            logger.debug("Focus removed from the active element")

            self.check_for_premium_redirect(job)
            easy_apply_button = self._find_easy_apply_button(job)
            self.check_for_premium_redirect(job)

            logger.debug("Retrieving job description")
            job_description = self._get_job_description()
            job.set_job_description(job_description)
            logger.debug(f"Job description set: {job_description[:100]}")

            logger.debug("Retrieving recruiter link")
            recruiter_link = self._get_job_recruiter()
            job.set_recruiter_link(recruiter_link)
            logger.debug(f"Recruiter link set: {recruiter_link}")

            # Try clicking the "Easy Apply" button
            try:
                self.handle_safety_reminder_modal(self.driver)

                logger.debug("Attempting to click 'Easy Apply' button using ActionChains")
                actions = ActionChains(self.driver)
                actions.move_to_element(easy_apply_button).click().perform()
                logger.debug("'Easy Apply' button clicked successfully")

                self.handle_safety_reminder_modal(self.driver)

                # Verify if the form has opened
                time.sleep(2)
                if not self._is_form_open():
                    logger.error("Form did not open after clicking 'Easy Apply' button.")
                    raise Exception("Failed to open form after clicking 'Easy Apply'.")
            except Exception as e:
                logger.warning(f"Failed to click 'Easy Apply' button using ActionChains: {e}, trying JavaScript click")
                try:
                    # Use JavaScript for clicking if ActionChains did not work
                    self.driver.execute_script("arguments[0].click();", easy_apply_button)
                    logger.debug("'Easy Apply' button clicked successfully via JavaScript")

                    # Check if the form opened again
                    time.sleep(2)
                    if not self._is_form_open():
                        logger.error("Form did not open after clicking 'Easy Apply' button using JavaScript.")
                        raise Exception("Failed to open form after clicking 'Easy Apply' with JavaScript.")
                except Exception as js_e:
                    logger.error(f"Failed to click 'Easy Apply' button using JavaScript: {js_e}")
                    raise  # Stop execution if the form does not open

            logger.debug("Passing job information to GPT Answerer")
            self.gpt_answerer.set_job(job)

            logger.debug("Filling out the application form")
            self._fill_application_form(job)
            logger.debug(f"Job application process completed successfully for job: {job}")

        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Failed to apply to job: {job}. Error traceback: {tb_str}")

            logger.debug("Discarding application due to failure")
            self._discard_application()

            raise Exception(f"Failed to apply to job! Original exception:\nTraceback:\n{tb_str}")

    def _find_easy_apply_button(self, job: Any) -> WebElement:
        """
        Finds the 'Easy Apply' button on the job page using various search methods.
        Args:
            job (Any): The job object containing details like the job link.
        Returns:
            WebElement: The Easy Apply button element if found.
        Raises:
            Exception: If the Easy Apply button cannot be found after several attempts.
        """
        logger.debug("Searching for 'Easy Apply' button")
        attempt = 0
        max_attempts = 3
        timeout = 10

        # Multiple search strategies to locate the Easy Apply button
        search_methods = [
            {
                'description': "Button within 'jobs-s-apply' div with class 'jobs-apply-button' and text containing 'Easy Apply'",
                'xpath': '//div[contains(@class, "jobs-s-apply")]//button[contains(@class, "jobs-apply-button") and .//span[text()="Easy Apply"]]',
                'count': 0
            },
            {
                'description': "Button with class 'jobs-apply-button' and normalized text 'Easy Apply'",
                'xpath': '//button[contains(@class, "jobs-apply-button") and normalize-space(text())="Easy Apply"]',
                'count': 0
            },
            {
                'description': "Button with ID 'ember40' and class 'artdeco-button--primary'",
                'xpath': "//button[@id='ember40' and contains(@class, 'artdeco-button--primary')]",
                'count': 0
            },
            {
                'description': "Button with aria-label containing 'Easy Apply to' and class 'jobs-apply-button'",
                'xpath': '//button[contains(@aria-label, "Easy Apply") and contains(@class, "jobs-apply-button")]',
                'count': 0
            },
            {
                'description': "Button with class 'jobs-apply-button' and text 'Easy Apply'",
                'xpath': '//button[contains(@class, "jobs-apply-button") and normalize-space(text())="Easy Apply"]',
                'count': 0
            },
            {
                'description': "Button using partial match for class 'artdeco-button--primary' and text 'Easy Apply'",
                'xpath': '//button[contains(@class, "artdeco-button--primary") and contains(., "Easy Apply")]',
                'count': 0
            },
            {
                'description': "CSS Selector for button with class 'artdeco-button__text' under #ember41",
                'css': '#ember41 > .artdeco-button__text',
                'count': 0
            },
            {
                'description': "CSS Selector for button with class 'artdeco-button__text' under #ember120",
                'css': '#ember120 > .artdeco-button__text',
                'count': 0
            },
            {
                'description': "XPath for span containing 'Easy Apply'",
                'xpath': '//span[contains(text(), "Easy Apply")]',
                'count': 0
            }
        ]

        while attempt < max_attempts:
            self.check_for_premium_redirect(job)
            self._scroll_page()

            try:
                WebDriverWait(self.driver, timeout).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                logger.warning("Page did not load within the timeout period")

            try:
                logger.info("Removing focus from the active element (likely URL bar)")
                self.driver.execute_script("document.activeElement.blur();")
                time.sleep(1)

                logger.info("Focusing on body element")
                body_element = self.driver.find_element(By.TAG_NAME, 'body')
                self.driver.execute_script("arguments[0].focus();", body_element)
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to reset focus: {e}")

            # Attempting to find the button using the defined search methods
            for method in search_methods:
                try:
                    logger.info(
                        f"Attempt {attempt + 1}: Searching for 'Easy Apply' button using {method['description']}")

                    if 'xpath' in method:
                        buttons = WebDriverWait(self.driver, timeout).until(
                            EC.presence_of_all_elements_located((By.XPATH, method['xpath']))
                        )
                    elif 'css' in method:
                        buttons = WebDriverWait(self.driver, timeout).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, method['css']))
                        )

                    for index, _ in enumerate(buttons):
                        try:
                            logger.info(f"Checking button at index {index + 1}")

                            if 'xpath' in method:
                                button = WebDriverWait(self.driver, timeout).until(
                                    EC.element_to_be_clickable(
                                        (By.XPATH, f'({method["xpath"]})[{index + 1}]')
                                    )
                                )
                            elif 'css' in method:
                                button = WebDriverWait(self.driver, timeout).until(
                                    EC.element_to_be_clickable(
                                        (By.CSS_SELECTOR, method['css'])
                                    )
                                )

                            if button.is_enabled() and button.is_displayed():
                                logger.info(
                                    f"'Easy Apply' button found and clickable using {method['description']} at index {index + 1}")
                                method['count'] += 1
                                self._save_search_statistics(search_methods)
                                return button
                            else:
                                logger.warning("Button is not enabled or displayed")
                        except Exception as e:
                            logger.warning(
                                f"Failed to click on 'Easy Apply' button at index {index + 1} using {method['description']}: {e}")

                except TimeoutException:
                    logger.warning(f"Timeout during search using {method['description']}")
                except Exception as e:
                    logger.warning(
                        f"Failed to find 'Easy Apply' button using {method['description']} on attempt {attempt + 1}: {e}")

            if attempt == 0:
                logger.info("Refreshing page to retry finding 'Easy Apply' button")
                self.driver.refresh()
                time.sleep(random.randint(3, 5))
            attempt += 1

        logger.error("No clickable 'Easy Apply' button found after all attempts")
        raise Exception("No clickable 'Easy Apply' button found")

    def _save_search_statistics(self, search_methods):
        """
        Saves statistics of the button search attempts to a file for tracking.
        Args:
            search_methods: List of search strategies used to locate the Easy Apply button.
        """
        file_path = 'easy_apply_search_stats.txt'
        stats = {}

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.split(':')
                        if len(parts) == 2:
                            description = parts[0].strip()
                            count = int(parts[1].strip())
                            stats[description] = count
            except Exception as e:
                logger.error(f"Failed to read existing search statistics: {e}")

        # Update statistics with new data
        for method in search_methods:
            if method['description'] in stats:
                stats[method['description']] += method['count']
            else:
                stats[method['description']] = method['count']

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for description, count in stats.items():
                    f.write(f"{description}: {count}\n")
            logger.info(f"Search statistics updated in {file_path}")
        except Exception as e:
            logger.error(f"Failed to save search statistics: {e}")

    def _get_job_description(self) -> str:
        """
        Extracts the job description from the LinkedIn job page.
        Returns:
            str: The extracted job description text.
        """
        logger.debug("Getting job description")
        try:
            try:
                see_more_button = self.driver.find_element(By.XPATH,
                                                           '//button[@aria-label="Click to see more description"]')
                actions = ActionChains(self.driver)
                actions.move_to_element(see_more_button).click().perform()
                time.sleep(2)
            except NoSuchElementException:
                logger.debug("See more button not found, skipping")

            description = self.driver.find_element(By.CLASS_NAME, 'jobs-description-content__text').text
            logger.debug("Job description retrieved successfully")
            return description
        except NoSuchElementException:
            tb_str = traceback.format_exc()
            logger.error(f"Job description not found: {tb_str}")
            raise Exception(f"Job description not found: \nTraceback:\n{tb_str}")
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error getting Job description: {tb_str}")
            raise Exception(f"Error getting Job description: \nTraceback:\n{tb_str}")

    def _get_job_recruiter(self):
        """
        Extracts the recruiter link from the LinkedIn job page if available.
        Returns:
            str: The URL of the recruiter profile or an empty string if not found.
        """
        logger.debug("Getting job recruiter information")
        try:
            hiring_team_section = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//h2[text()="Meet the hiring team"]'))
            )
            logger.debug("Hiring team section found")

            recruiter_elements = hiring_team_section.find_elements(By.XPATH,
                                                                   './/following::a[contains(@href, "linkedin.com/in/")]')

            if recruiter_elements:
                recruiter_element = recruiter_elements[0]
                recruiter_link = recruiter_element.get_attribute('href')
                logger.debug(f"Job recruiter link retrieved successfully: {recruiter_link}")
                return recruiter_link
            else:
                logger.info("Recruiter link not found in the 'Meet the hiring team' section.")
                return ""

        except TimeoutException:
            logger.info(
                "The 'Meet the hiring team' section is not present on the page.")
            return ""

        except Exception as e:
            logger.error(f"An unexpected error occurred while retrieving recruiter information: {e}", exc_info=True)
            return ""

    def _scroll_page(self) -> None:
        logger.debug("Scrolling the page")
        scrollable_element = self.driver.find_element(By.TAG_NAME, 'html')
        utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=False)
        utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=True)

    def _fill_application_form(self, job):
        logger.debug(f"Filling out application form for job: {job}")

        form_filled = False
        try:
            while not form_filled:
                self.fill_up(job)
                form_filled = self._next_or_submit()
                if form_filled:
                    logger.debug("Application form submitted successfully")
                    return
        except Exception as e:
            logger.error(f"Form filling failed: {e}. Skipping this job.")
            self._discard_application()

    def _next_or_submit(self):
        logger.debug("Clicking 'Next' or 'Submit' button")
        next_button = self.driver.find_element(By.CLASS_NAME, "artdeco-button--primary")
        button_text = next_button.text.lower()

        if 'submit application' in button_text:
            logger.debug("Submit button found, submitting application")
            self._unfollow_company()
            time.sleep(random.uniform(1.5, 2.5))
            next_button.click()
            time.sleep(random.uniform(1.5, 2.5))
            return True
        else:
            time.sleep(random.uniform(1.5, 2.5))
            next_button.click()

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'jobs-easy-apply-content'))
            )
            time.sleep(random.uniform(3.0, 5.0))
            self._check_for_errors()
            return False

    def _unfollow_company(self) -> None:
        try:
            logger.debug("Unfollowing company")
            follow_checkbox = self.driver.find_element(
                By.XPATH, "//label[contains(.,'to stay up to date with their page.')]")
            follow_checkbox.click()
        except Exception as e:
            logger.warning(f"Failed to unfollow company: {e}")

    def _check_for_errors(self) -> None:
        logger.debug("Checking for form errors")
        error_elements = self.driver.find_elements(By.CLASS_NAME, 'artdeco-inline-feedback--error')
        if error_elements:
            error_texts = [e.text for e in error_elements]
            logger.error(f"Form submission failed with errors: {error_texts}")
            raise Exception(f"Failed answering or file upload. {error_texts}")

    def _discard_application(self) -> None:
        logger.debug("Discarding application")
        try:
            self.driver.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss').click()
            time.sleep(random.uniform(3, 5))
            self.driver.find_elements(By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn')[0].click()
            time.sleep(random.uniform(3, 5))
        except Exception as e:
            logger.warning(f"Failed to discard application: {e}")

    def fill_up(self, job) -> None:
        logger.debug(f"Filling up form sections for job: {job}")

        try:
            easy_apply_content = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'jobs-easy-apply-content'))
            )

            pb4_elements = easy_apply_content.find_elements(By.CLASS_NAME, 'pb4')
            for element in pb4_elements:
                self._process_form_element(element, job)

            self._fill_additional_questions()
        except Exception as e:
            logger.error(f"Failed to find form elements: {e}")

    def _process_form_element(self, element: WebElement, job) -> None:
        logger.debug("Processing form element")

        if self._is_upload_field(element):
            self._handle_upload_fields(element, job)
        else:
            try:
                label_element = element.find_element(By.XPATH,
                                                     '//label[@data-test-text-selectable-option__label="I do not have any adjustment requirements"]')
                label_element.click()
                logger.debug("Successfully clicked on the label")
            except Exception as e:
                logger.warning(f"Failed to click on the label: {e}")

    def _is_upload_field(self, element: WebElement) -> bool:
        is_upload = bool(element.find_elements(By.XPATH, ".//input[@type='file']"))
        logger.debug(f"Element is upload field: {is_upload}")
        return is_upload

    def _handle_upload_fields(self, element: WebElement, job) -> None:
        logger.debug("Handling upload fields")

        resume_uploaded = False

        try:
            show_more_button = self.driver.find_element(By.XPATH,
                                                        "//button[contains(@aria-label, 'Show') and contains(@aria-label, 'more resumes')]")
            show_more_button.click()
            logger.debug("Clicked 'Show more resumes' button")
        except NoSuchElementException:
            logger.debug("'Show more resumes' button not found, continuing...")

        file_upload_elements = self.driver.find_elements(By.XPATH, "//input[@type='file']")
        for upload_element in file_upload_elements:
            parent = upload_element.find_element(By.XPATH, "..")

            if 'upload-resume' in upload_element.get_attribute('id') and not resume_uploaded:
                logger.debug("Detected resume upload input by ID")

                # Step 1: Check if resume file path is valid and if the file is already uploaded
                resume_filename = os.path.basename(self.resume_path) if self.resume_path else None

                if resume_filename and self.resume_path and os.path.isfile(self.resume_path):
                    # Check if the resume is already uploaded
                    if self.is_resume_already_uploaded(self.driver, resume_filename):
                        logger.info(f"Resume '{resume_filename}' is already uploaded. Skipping re-upload.")
                        resume_uploaded = True
                        continue

                    # Upload the resume if it hasn't been uploaded yet
                    logger.debug(f"Uploading resume from path: {self.resume_path}")
                    upload_element.send_keys(os.path.abspath(self.resume_path))
                    resume_uploaded = True
                    continue
                else:
                    logger.debug("Resume path not found or invalid, generating new resume")
                    self._create_and_upload_resume(upload_element, job)
                    resume_uploaded = True
                    continue

            if not resume_uploaded:
                self.driver.execute_script("arguments[0].classList.remove('hidden')", upload_element)

                output = self.gpt_answerer.resume_or_cover(parent.text.lower())

                if 'resume' in output:
                    logger.debug("Uploading resume based on text detection")
                    if self.resume_path is not None and os.path.isfile(self.resume_path):
                        # Check again before uploading based on text detection
                        resume_filename = os.path.basename(self.resume_path)
                        if self.is_resume_already_uploaded(self.driver, resume_filename):
                            logger.info(
                                f"Resume '{resume_filename}' is already uploaded based on text detection. Skipping upload.")
                            resume_uploaded = True
                            continue

                        upload_element.send_keys(os.path.abspath(self.resume_path))
                        logger.debug(f"Resume uploaded from path: {self.resume_path}")
                        resume_uploaded = True
                    else:
                        logger.debug("Resume path not found or invalid, generating new resume")
                        self._create_and_upload_resume(upload_element, job)
                        resume_uploaded = True
                elif 'cover' in output:
                    logger.debug("Uploading cover letter based on text detection")
                    self._create_and_upload_cover_letter(upload_element, job)

        logger.debug("Finished handling upload fields")

    def _create_and_upload_resume(self, element, job):
        logger.debug("Starting the process of creating and uploading resume.")
        folder_path = 'generated_cv'

        try:
            os.makedirs(folder_path, exist_ok=True)
            logger.debug(f"Ensured directory exists at path: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to create directory: {folder_path}. Error: {e}")
            raise

        while True:
            try:
                candidate_first_name = self.job_application_profile.personal_information.name
                candidate_last_name = self.job_application_profile.personal_information.surname
                timestamp = int(time.time())
                file_name = f"CV_{candidate_first_name}_{candidate_last_name}_{timestamp}.pdf"
                file_path_pdf = os.path.join(folder_path, file_name)
                logger.debug(f"Generated file path for resume: {file_path_pdf}")

                logger.debug(f"Generating resume for job: {job.title} at {job.company}")
                resume_pdf_base64 = self.resume_generator_manager.pdf_base64(job_description_text=job.description)
                with open(file_path_pdf, "xb") as f:
                    f.write(base64.b64decode(resume_pdf_base64))
                logger.debug(f"Resume successfully generated and saved to: {file_path_pdf}")
                break
            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = e.response.headers.get('retry-after')
                    retry_after_ms = e.response.headers.get('retry-after-ms')

                    if retry_after:
                        wait_time = int(retry_after)
                        logger.warning(f"Rate limit exceeded, waiting {wait_time} seconds before retrying...")
                    elif retry_after_ms:
                        wait_time = int(retry_after_ms) / 1000.0
                        logger.warning(f"Rate limit exceeded, waiting {wait_time} milliseconds before retrying...")
                    else:
                        wait_time = 20
                        logger.warning(f"Rate limit exceeded, waiting {wait_time} seconds before retrying...")

                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Failed to generate resume: {e}")
                tb_str = traceback.format_exc()
                logger.error(f"Traceback: {tb_str}")
                if "RateLimitError" in str(e):
                    logger.warning("Rate limit error encountered, retrying...")
                    time.sleep(20)
                else:
                    raise

        file_size = os.path.getsize(file_path_pdf)
        max_file_size = 2 * 1024 * 1024  # 2 MB
        logger.debug(f"Resume file size: {file_size} bytes")
        if file_size > max_file_size:
            logger.error(f"Resume file size exceeds 2 MB: {file_size} bytes")
            raise ValueError("Resume file size exceeds the maximum limit of 2 MB.")

        allowed_extensions = {'.pdf', '.doc', '.docx'}
        file_extension = os.path.splitext(file_path_pdf)[1].lower()
        logger.debug(f"Resume file extension: {file_extension}")
        if file_extension not in allowed_extensions:
            logger.error(f"Invalid resume file format: {file_extension}")
            raise ValueError("Resume file format is not allowed. Only PDF, DOC, and DOCX formats are supported.")

        try:
            logger.debug(f"Uploading resume from path: {file_path_pdf}")
            element.send_keys(os.path.abspath(file_path_pdf))
            job.pdf_path = os.path.abspath(file_path_pdf)
            time.sleep(2)
            logger.debug(f"Resume created and uploaded successfully: {file_path_pdf}")
        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Resume upload failed: {tb_str}")
            raise Exception(f"Upload failed: \nTraceback:\n{tb_str}")

    def _create_and_upload_cover_letter(self, element: WebElement, job) -> None:
        logger.debug("Starting the process of creating and uploading cover letter.")

        cover_letter_text = self.gpt_answerer.answer_question_textual_wide_range("cover_letter")

        folder_path = 'generated_cv'

        try:
            os.makedirs(folder_path, exist_ok=True)
            logger.debug(f"Ensured directory exists at path: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to create directory: {folder_path}. Error: {e}")
            raise

        while True:
            try:
                timestamp = int(time.time())
                file_path_pdf = os.path.join(folder_path, f"Cover_Letter_{timestamp}.pdf")
                logger.debug(f"Generated file path for cover letter: {file_path_pdf}")

                styles = getSampleStyleSheet()
                style = styles["Normal"]
                style.fontName = "Helvetica"
                style.fontSize = 12
                style.leading = 15

                story = [Paragraph(cover_letter_text, style)]

                doc = SimpleDocTemplate(
                    file_path_pdf,
                    pagesize=A4,
                    rightMargin=20,
                    leftMargin=20,
                    topMargin=20,
                    bottomMargin=20
                )

                doc.build(story)

                logger.debug(f"Cover letter successfully generated and saved to: {file_path_pdf}")
                break
            except Exception as e:
                logger.error(f"Failed to generate cover letter: {e}")
                tb_str = traceback.format_exc()
                logger.error(f"Traceback: {tb_str}")
                raise

        file_size = os.path.getsize(file_path_pdf)
        max_file_size = 2 * 1024 * 1024  # 2 MB
        logger.debug(f"Cover letter file size: {file_size} bytes")
        if file_size > max_file_size:
            logger.error(f"Cover letter file size exceeds 2 MB: {file_size} bytes")
            raise ValueError("Cover letter file size exceeds the maximum limit of 2 MB.")

        allowed_extensions = {'.pdf', '.doc', '.docx'}
        file_extension = os.path.splitext(file_path_pdf)[1].lower()
        logger.debug(f"Cover letter file extension: {file_extension}")
        if file_extension not in allowed_extensions:
            logger.error(f"Invalid cover letter file format: {file_extension}")
            raise ValueError("Cover letter file format is not allowed. Only PDF, DOC, and DOCX formats are supported.")

        try:
            logger.debug(f"Uploading cover letter from path: {file_path_pdf}")
            element.send_keys(os.path.abspath(file_path_pdf))
            job.cover_letter_path = os.path.abspath(file_path_pdf)
            time.sleep(2)
            logger.debug(f"Cover letter created and uploaded successfully: {file_path_pdf}")
        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Cover letter upload failed: {tb_str}")
            raise Exception(f"Upload failed: \nTraceback:\n{tb_str}")

    def _fill_additional_questions(self) -> None:
        logger.debug("Filling additional questions")
        form_sections = self.driver.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-section__grouping')
        for section in form_sections:
            self._process_form_section(section)

    def _process_form_section(self, section: WebElement) -> None:
        logger.debug("Processing form section")
        if self._handle_terms_of_service(section):
            logger.debug("Handled terms of service")
            return
        if self._find_and_handle_radio_question(section):
            logger.debug("Handled radio question")
            return
        if self._find_and_handle_textbox_question(section):
            logger.debug("Handled textbox question")
            return
        if self._find_and_handle_date_question(section):
            logger.debug("Handled date question")
            return
        if self._find_and_handle_checkbox_question(section):
            logger.debug("Handled checkbox question")
            return
        if self._find_and_handle_dropdown_question(section):
            logger.debug("Handled dropdown question")
            return

    def _handle_terms_of_service(self, element: WebElement) -> bool:
        checkbox = element.find_elements(By.TAG_NAME, 'label')
        if checkbox and any(
                term in checkbox[0].text.lower() for term in ['terms of service', 'privacy policy', 'terms of use']):
            checkbox[0].click()
            logger.debug("Clicked terms of service checkbox")
            return True
        return False

    def _find_and_handle_radio_question(self, section: WebElement) -> bool:
        question = section.find_element(By.CLASS_NAME, 'jobs-easy-apply-form-element')
        radios = question.find_elements(By.CLASS_NAME, 'fb-text-selectable__option')
        if radios:
            question_text = section.text.lower()
            options = [radio.text.lower() for radio in radios]

            existing_answer = None
            for item in self.all_data:
                if self._sanitize_text(question_text) in item['question'] and item['type'] == 'radio':
                    existing_answer = item
                    break
            if existing_answer:
                self._select_radio(radios, existing_answer['answer'])
                logger.debug("Selected existing radio answer")
                return True

            answer = self.gpt_answerer.answer_question_from_options(question_text, options)
            self._save_questions_to_json({'type': 'radio', 'question': question_text, 'answer': answer})
            self._select_radio(radios, answer)
            logger.debug("Selected new radio answer")
            return True
        return False

    def _select_radio(self, radios: List[WebElement], answer: str) -> None:
        logger.debug(f"Selecting radio option: {answer}")
        for radio in radios:
            if answer in radio.text.lower():
                radio.find_element(By.TAG_NAME, 'label').click()
                return
        radios[-1].find_element(By.TAG_NAME, 'label').click()

    def _find_and_handle_textbox_question(self, section: WebElement) -> bool:
        logger.debug("Searching for text fields in the section.")
        text_fields = section.find_elements(By.TAG_NAME, 'input') + section.find_elements(By.TAG_NAME, 'textarea')

        if text_fields:
            text_field = text_fields[0]
            question_text = section.find_element(By.TAG_NAME, 'label').text.lower().strip()
            logger.debug(f"Found text field with label: {question_text}")

            is_numeric = self._is_numeric_field(text_field)
            logger.debug(f"Is the field numeric? {'Yes' if is_numeric else 'No'}")

            existing_answer = None
            question_type = 'numeric' if is_numeric else 'textbox'

            for item in self.all_data:
                if self._sanitize_text(item['question']) == self._sanitize_text(question_text) and item.get('type') == question_type:
                    existing_answer = item
                    logger.debug(f"Found existing answer in the data: {existing_answer['answer']}")
                    break

            if existing_answer:
                self._enter_text(text_field, existing_answer['answer'])
                logger.debug("Entered existing answer into the textbox.")
                time.sleep(1)
                text_field.send_keys(Keys.ARROW_DOWN)
                text_field.send_keys(Keys.ENTER)
                logger.debug("Selected first option from the dropdown.")
                return True

            if is_numeric:
                answer = self.gpt_answerer.answer_question_numeric(question_text)
                logger.debug(f"Generated numeric answer: {answer}")
            else:
                answer = self.gpt_answerer.answer_question_textual_wide_range(question_text)
                logger.debug(f"Generated textual answer: {answer}")

            self._save_questions_to_json({'type': question_type, 'question': question_text, 'answer': answer})
            self._enter_text(text_field, answer)
            logger.debug("Entered new answer into the textbox and saved it to JSON.")

            time.sleep(1)
            text_field.send_keys(Keys.ARROW_DOWN)
            text_field.send_keys(Keys.ENTER)
            logger.debug("Selected first option from the dropdown.")
            return True

        logger.debug("No text fields found in the section.")
        return False

    def _is_numeric_field(self, field: WebElement) -> bool:
        field_type = field.get_attribute('type').lower()
        field_id = field.get_attribute("id").lower()
        is_numeric = 'numeric' in field_id or field_type == 'number' or ('text' == field_type and 'numeric' in field_id)
        logger.debug(f"Field type: {field_type}, Field ID: {field_id}, Is numeric: {is_numeric}")
        return is_numeric

    def _enter_text(self, element: WebElement, text: str) -> None:
        logger.debug(f"Entering text: {text}")
        element.clear()
        element.send_keys(text)

    def _find_and_handle_date_question(self, section: WebElement) -> bool:
        logger.debug("Searching for date fields in the section.")
        date_fields = section.find_elements(By.CLASS_NAME, 'artdeco-datepicker__input')

        if date_fields:
            date_field = date_fields[0]
            question_text = section.text.lower().strip()

            placeholder = date_field.get_attribute('placeholder')
            if placeholder:
                logger.debug(f"Detected date format placeholder: {placeholder}")
                try:
                    date_format = self._infer_date_format_from_placeholder(placeholder)
                except Exception as e:
                    logger.error(f"Failed to infer date format from placeholder: {e}. Defaulting to %m/%d/%Y.")
                    date_format = "%m/%d/%Y"
            else:
                logger.warning("No placeholder found. Defaulting to %m/%d/%Y.")
                date_format = "%m/%d/%Y"

            logger.debug(f"Classifying question for date input: {question_text}")
            try:
                answer_date = self.gpt_answerer.answer_question_date(question_text)
                answer_text = answer_date.strftime(date_format)
            except Exception as e:
                logger.error(f"Error generating answer date from model: {e}")
                return False

            try:
                self._enter_text(date_field, answer_text)
                logger.debug(f"Entered date '{answer_text}' in the format {date_format}.")
                return True
            except Exception as e:
                logger.error(f"Failed to enter date: {e}")
                return False

        logger.debug("No date fields found in the section.")
        return False

    def _infer_date_format_from_placeholder(self, placeholder: str) -> str:
        format_map = {
            "dd": "%d",
            "mm": "%m",
            "yyyy": "%Y",
            "yy": "%y"
        }

        for key, value in format_map.items():
            placeholder = placeholder.replace(key, value)

        logger.debug(f"Inferred date format: {placeholder}")
        return placeholder

    def _find_and_handle_checkbox_question(self, section: WebElement) -> bool:
        logger.debug("Searching for checkbox fields in the section.")
        checkboxes = section.find_elements(By.XPATH, ".//input[@type='checkbox']")

        if checkboxes:
            question_text_element = section.find_elements(By.CLASS_NAME, 'fb-form-element-label__title')
            question_text = question_text_element[0].text.lower().strip() if question_text_element else "unknown question"
            logger.debug(f"Found checkbox group with label: {question_text}")

            options = []
            for checkbox in checkboxes:
                option_label = section.find_element(By.XPATH, f".//label[@for='{checkbox.get_attribute('id')}']").text.strip()
                options.append(option_label)

            logger.debug(f"Available checkbox options: {options}")

            existing_answers = []
            for item in self.all_data:
                if self._sanitize_text(question_text) in item['question'] and item['type'] == 'checkbox':
                    existing_answers = item['answer']
                    break

            if existing_answers:
                logger.debug(f"Found existing answers: {existing_answers}")
                for checkbox, option in zip(checkboxes, options):
                    if option in existing_answers and not checkbox.is_selected():
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                        self.driver.execute_script("arguments[0].click();", checkbox)
                        logger.debug(f"Selected checkbox for option: {option}")
                return True

            logger.debug(f"No existing answers found, querying model for: {question_text}")
            answers = self.gpt_answerer.answer_question_from_options(question_text, options)
            logger.debug(f"Model provided answers: {answers}")

            self._save_questions_to_json({'type': 'checkbox', 'question': question_text, 'answer': answers})

            for checkbox, option in zip(checkboxes, options):
                if option in answers and not checkbox.is_selected():
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                    self.driver.execute_script("arguments[0].click();", checkbox)
                    logger.debug(f"Selected checkbox for option: {option}")
            return True

        logger.debug("No checkbox fields found in the section.")
        return False

    def _find_and_handle_dropdown_question(self, section: WebElement) -> bool:
        try:
            question = section.find_element(By.CLASS_NAME, 'jobs-easy-apply-form-element')

            dropdowns = question.find_elements(By.TAG_NAME, 'select')
            if not dropdowns:
                dropdowns = section.find_elements(By.CSS_SELECTOR, '[data-test-text-entity-list-form-select]')

            if dropdowns:
                dropdown = dropdowns[0]
                select = Select(dropdown)
                options = [option.text for option in select.options if option.text != "Select an option"]

                logger.debug(f"Dropdown options found: {options}")

                try:
                    question_text = question.find_element(By.TAG_NAME, 'label').text.lower().strip()
                except NoSuchElementException:
                    logger.warning("Label not found, trying to extract question text from other elements")
                    question_text = section.text.lower().strip()

                logger.debug(f"Processing dropdown question: {question_text}")

                existing_answer = None
                for item in self.all_data:
                    if self._sanitize_text(question_text) in item['question'] and item['type'] == 'dropdown':
                        existing_answer = item['answer']
                        break

                if existing_answer:
                    logger.debug(f"Found existing answer for question '{question_text}': {existing_answer}")
                else:
                    existing_answer = self.gpt_answerer.answer_question_from_options(question_text, options)
                    logger.debug(f"Model provided answer: {existing_answer}")
                    self._save_questions_to_json({'type': 'dropdown', 'question': question_text, 'answer': existing_answer})

                if existing_answer in options:
                    logger.debug(f"Updating selection to: {existing_answer}")
                    self._select_dropdown_option(select, existing_answer)
                else:
                    logger.error(f"Answer '{existing_answer}' is not a valid option in the dropdown")
                    raise Exception(f"Invalid option selected: {existing_answer}")

                return True
            else:
                logger.debug("No dropdown found in section.")
                return False

        except TimeoutException:
            logger.error("Timeout while trying to locate dropdown")
            return False
        except Exception as e:
            logger.warning(f"Failed to handle dropdown or combobox question: {e}", exc_info=True)
            return False

    def _select_dropdown_option(self, select: Select, text: str) -> None:
        try:
            select.select_by_visible_text(text)
            logger.debug(f"Selected option: {text}")
        except Exception as e:
            logger.error(f"Failed to select option '{text}': {e}")

    def _save_questions_to_json(self, question_data: dict) -> None:
        """
        Save question data to a JSON file, with filtering to exclude company-specific or unsuitable questions.

        Args:
            question_data (dict): The question and answer data to be saved.
        """
        output_file = 'answers.json'
        question_data['question'] = self._sanitize_text(question_data['question'])
        logger.debug(f"Saving question data to JSON: {question_data}")

        # List of keywords to exclude certain questions from being saved
        exclusion_keywords = ["why us", "summary", "cover letter", "your message", "want to work"]

        # Check if the question contains any exclusion keywords
        if any(keyword in question_data['question'].lower() for keyword in exclusion_keywords):
            logger.info(f"Skipping saving question due to company-specific keywords: {question_data['question']}")
            return  # Skip saving this question if it's company-specific

        try:
            with open(output_file, 'r') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("JSON file format is incorrect. Expected a list of questions.")
                except json.JSONDecodeError:
                    logger.error("JSON decoding failed")
                    data = []
        except FileNotFoundError:
            logger.warning("JSON file not found, creating new file")
            data = []

        if question_data in data:
            logger.info(f"Duplicate question found, skipping save: {question_data['question']}")
            return

        data.append(question_data)
        try:
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.debug("Question data saved successfully to JSON")
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error saving questions data to JSON file: {tb_str}")
            raise Exception(f"Error saving questions data to JSON file: \nTraceback:\n{tb_str}")

    def _sanitize_text(self, text: str) -> str:
        sanitized_text = text.lower().strip().replace('"', '').replace('\\', '')
        sanitized_text = re.sub(r'[\x00-\x1F\x7F]', '', sanitized_text).replace('\n', ' ').replace('\r', '').rstrip(',')
        logger.debug(f"Sanitized text: {sanitized_text}")
        return sanitized_text

    def _is_form_open(self) -> bool:
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'jobs-easy-apply-content'))
            )
            return True
        except TimeoutException:
            return False

    def handle_safety_reminder_modal(driver, timeout=5):
        """
        Handles the job safety reminder modal window.
        If the modal is present, clicks the 'Continue applying' button.

        Args:
            driver (webdriver): The Selenium WebDriver instance.
            timeout (int): Time to wait for the modal window to appear (default: 5 seconds).
        """
        try:
            logger.debug("Checking for the presence of the job safety reminder modal...")
            # Check if the 'Continue applying' button is present
            continue_button = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//span[text()='Continue applying']/ancestor::button"))
            )
            logger.info("Job safety reminder modal detected. Clicking the 'Continue applying' button.")
            continue_button.click()
            logger.debug("'Continue applying' button clicked successfully.")
        except TimeoutException:
            logger.info("Job safety reminder modal not found. Continuing with the process.")

    def is_resume_already_uploaded(driver, resume_filename: str) -> bool:
        """
        Checks if the resume with the given filename is already uploaded.

        Args:
            driver (webdriver): The Selenium WebDriver instance.
            resume_filename (str): The name of the resume file to check.

        Returns:
            bool: True if the resume is already uploaded, False otherwise.
        """
        try:
            logger.debug(f"Checking if the resume '{resume_filename}' is already uploaded.")
            uploaded_resumes = driver.find_elements(By.XPATH,
                                                    "//h3[contains(@class, 'jobs-document-upload-redesign-card__file-name')]")
            for resume_element in uploaded_resumes:
                if resume_element.text.strip() == resume_filename:
                    logger.info(f"Resume '{resume_filename}' is already uploaded.")
                    return True
            logger.info(f"Resume '{resume_filename}' not found in uploaded documents.")
        except Exception as e:
            logger.error(f"Error while checking uploaded resumes: {str(e)}")

        return False
