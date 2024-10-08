import json
import os
import random
import threading
import time
from itertools import product
from pathlib import Path
import re

from inputimeout import inputimeout, TimeoutOccurred
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

import src.utils as utils
from app_config import MINIMUM_WAIT_TIME
from src.job import Job
from src.aihawk_easy_applier import AIHawkEasyApplier
from loguru import logger


class EnvironmentKeys:
    def __init__(self):
        logger.debug("Initializing EnvironmentKeys")
        self.skip_apply = self._read_env_key_bool("SKIP_APPLY")
        self.disable_description_filter = self._read_env_key_bool("DISABLE_DESCRIPTION_FILTER")
        logger.debug(f"EnvironmentKeys initialized: skip_apply={self.skip_apply}, disable_description_filter={self.disable_description_filter}")

    @staticmethod
    def _read_env_key(key: str) -> str:
        value = os.getenv(key, "")
        logger.debug(f"Read environment key {key}: {value}")
        return value

    @staticmethod
    def _read_env_key_bool(key: str) -> bool:
        value = os.getenv(key) == "True"
        logger.debug(f"Read environment key {key} as bool: {value}")
        return value


class AIHawkJobManager:
    def __init__(self, driver):
        logger.debug("Initializing AIHawkJobManager")
        self.driver = driver
        self.set_old_answers = []
        self.easy_applier_component = None
        self.job_application_profile = None
        self.seen_jobs = []
        logger.debug("AIHawkJobManager initialized successfully")

    def set_parameters(self, parameters):
        logger.debug("Setting parameters for AIHawkJobManager")
        self.company_blacklist = parameters.get('company_blacklist', []) or []
        self.title_blacklist = parameters.get('title_blacklist', []) or []
        self.positions = parameters.get('positions', [])
        self.locations = parameters.get('locations', [])
        self.apply_once_at_company = parameters.get('apply_once_at_company', False)
        self.base_search_url = self.get_base_search_url(parameters)
        self.seen_jobs = []

        job_applicants_threshold = parameters.get('job_applicants_threshold', {})
        self.min_applicants = job_applicants_threshold.get('min_applicants', 0)
        self.max_applicants = job_applicants_threshold.get('max_applicants', float('inf'))

        resume_path = parameters.get('uploads', {}).get('resume', None)
        self.resume_path = Path(resume_path) if resume_path and Path(resume_path).exists() else None
        self.output_file_directory = Path(parameters['outputFileDirectory'])
        self.env_config = EnvironmentKeys()
        self.parameters = parameters
        logger.debug("Parameters set successfully")

    def set_job_application_profile(self, job_application_profile):
        logger.debug("Setting job application profile in LinkedInJobManager")
        self.job_application_profile = job_application_profile

    def set_gpt_answerer(self, gpt_answerer):
        logger.debug("Setting GPT answerer")
        self.gpt_answerer = gpt_answerer

    def set_resume_generator_manager(self, resume_generator_manager):
        logger.debug("Setting resume generator manager")
        self.resume_generator_manager = resume_generator_manager

    def get_input_with_timeout(self, prompt, timeout_duration):
        user_input = [None]

        # Check if code is running in PyCharm
        is_pycharm = 'PYCHARM_HOSTED' in os.environ

        if is_pycharm:
            # Input with timeout is not supported in PyCharm console
            logger.warning("Input with timeout is not supported in PyCharm console. Proceeding without user input.")
            return ''
        else:
            # Use threading to implement timeout
            def input_thread():
                user_input[0] = input(prompt).strip().lower()

            thread = threading.Thread(target=input_thread)
            thread.daemon = True
            thread.start()
            thread.join(timeout_duration)
            if thread.is_alive():
                logger.debug("Input timed out")
                return ''
            else:
                return user_input[0]

    def wait_or_skip(self, time_left):
        """Method for waiting or skipping the sleep time based on user input"""
        if time_left > 0:
            user_input = self.get_input_with_timeout(
                prompt=f"Sleeping for {time_left} seconds. Press 'y' to skip waiting. Timeout 60 seconds: ",
                timeout_duration=60)
            if user_input == 'y':
                logger.debug("User chose to skip waiting.")
                utils.printyellow("User skipped waiting.")
            else:
                logger.debug(f"Sleeping for {time_left} seconds as user chose not to skip.")
                utils.printyellow(f"Sleeping for {time_left} seconds.")
                time.sleep(time_left)


    def start_applying(self):
        logger.debug("Starting job application process")
        self.easy_applier_component = AIHawkEasyApplier(
            self.driver,
            self.resume_path,
            self.set_old_answers,
            self.gpt_answerer,
            self.resume_generator_manager,
            job_application_profile=self.job_application_profile  # Pass the job_application_profile here
        )
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        page_sleep = 0
        minimum_time = MINIMUM_WAIT_TIME
        minimum_page_time = time.time() + minimum_time

        for position, location in searches:
            location_url = "&location=" + location
            job_page_number = -1
            logger.debug(f"Starting the search for {position} in {location}.")

            try:
                while True:
                    page_sleep += 1
                    job_page_number += 1
                    logger.debug(f"Going to job page {job_page_number}")
                    self.next_job_page(position, location_url, job_page_number)
                    time.sleep(random.uniform(1.5, 3.5))
                    logger.debug("Starting the application process for this page...")

                    try:
                        jobs = self.get_jobs_from_page()
                        if not jobs:
                            # Attempt to find and click the search button
                            try:
                                search_button = self.driver.find_element(By.CLASS_NAME, "jobs-search-box__submit-button")
                                search_button.click()
                                logger.debug("Clicked the search button to reload jobs.")
                                time.sleep(random.uniform(1.5, 3.5))
                                jobs = self.get_jobs_from_page()
                            except NoSuchElementException:
                                logger.warning("Search button not found.")
                            except Exception as e:
                                logger.error(f"Error while trying to click the search button: {e}")

                            if not jobs:
                                utils.printyellow("No more jobs found on this page. Exiting loop.")
                                break
                    except Exception as e:
                        logger.error(f"Failed to retrieve jobs: {e}")
                        break

                    try:
                        self.apply_jobs()
                    except Exception as e:
                        logger.error(f"Error during job application: {e}")
                        continue

                    logger.debug("Applying to jobs on this page has been completed!")

                    time_left = minimum_page_time - time.time()

                    # Use the wait_or_skip function for sleeping
                    self.wait_or_skip(time_left)

                    minimum_page_time = time.time() + minimum_time

                    if page_sleep % 5 == 0:
                        sleep_time = random.randint(5, 34)
                        # Use the wait_or_skip function for extended sleep
                        self.wait_or_skip(sleep_time)
                        page_sleep += 1
            except Exception as e:
                logger.error("Unexpected error during job search: %s", e)
                utils.printred(f"Unexpected error: {e}")
                continue

            time_left = minimum_page_time - time.time()

            # Use the wait_or_skip function again before moving to the next search
            self.wait_or_skip(time_left)

            minimum_page_time = time.time() + minimum_time

            if page_sleep % 5 == 0:
                sleep_time = random.randint(50, 90)
                # Use the wait_or_skip function for a longer sleep period
                self.wait_or_skip(sleep_time)
                page_sleep += 1

    def get_jobs_from_page(self):

        try:
            try:
                no_jobs_element = self.driver.find_element(By.CLASS_NAME, 'jobs-search-no-results-banner')
            except NoSuchElementException:
                try:

                    no_jobs_element = self.driver.find_element(By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand')
                except NoSuchElementException:
                    no_jobs_element = None

            if no_jobs_element and ('No matching jobs found' in no_jobs_element.text or 'unfortunately, things aren' in self.driver.page_source.lower()):
                utils.printyellow("No matching jobs found on this page.")
                logger.debug("No matching jobs found on this page, skipping.")
                return []

        except NoSuchElementException:
            pass

        try:
            job_results = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
            utils.scroll_slow(self.driver, job_results)
            # utils.scroll_slow(self.driver, job_results, step=300, reverse=True)

            job_list_elements = self.driver.find_elements(By.CLASS_NAME, 'scaffold-layout__list-container')[
                0].find_elements(By.CLASS_NAME, 'jobs-search-results__list-item')
            if not job_list_elements:
                logger.debug("No job class elements found on page, skipping.")
                return []

            return job_list_elements

        except NoSuchElementException:
            logger.debug("No job results found on the page.")
            return []

        except Exception as e:
            logger.error(f"Error while fetching job elements: {e}")
            return []

    def apply_jobs(self):
        try:
            # Check if no matching jobs are found on the current page
            no_jobs_element = self.driver.find_element(By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand')
            if 'No matching jobs found' in no_jobs_element.text or 'unfortunately, things aren' in self.driver.page_source.lower():
                logger.debug("No matching jobs found on this page, skipping")
                return
        except NoSuchElementException:
            pass
    
        # Find the job results container and job elements
        job_results = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
        
        # utils.scroll_slow(self.driver, job_results)
        # utils.scroll_slow(self.driver, job_results, step=300, reverse=True)

        job_list_elements = job_results.find_elements(By.CLASS_NAME, 'jobs-search-results__list-item')
    
        if not job_list_elements:
            utils.printyellow("No job class elements found on page, moving to next page.")
            logger.debug("No job class elements found on page, skipping")
            return

        job_list = [Job(*self.extract_job_information_from_tile(job_element)) for job_element in job_list_elements]

        for job in job_list:
            logger.debug(f"Starting applicant count search for job: {job.title} at {job.company}")
    
            try:
                # Use the new function to check the applicant count and decide whether to continue or skip
                if not self.check_applicant_count(job):
                    utils.printyellow(f"Skipping {job.title} at {job.company} due to applicant count criteria.")
                    logger.debug(f"Skipping {job.title} at {job.company} based on applicant count.")
                    self.write_to_file(job, "skipped_due_to_applicants")
                    continue
    
                # Continue with other conditions and apply if not blacklisted or already applied
                if self.is_blacklisted(job.title, job.company, job.link):
                    logger.debug("Job blacklisted: %s at %s", job.title, job.company)
                    self.write_to_file(job, "skipped")
                    continue
    
                if self.is_already_applied_to_job(job.title, job.company, job.link):
                    self.write_to_file(job, "skipped")
                    continue
    
                if self.is_already_applied_to_company(job.company):
                    self.write_to_file(job, "skipped")
                    continue
    
                # Apply to the job if eligible
                if job.apply_method not in {"Continue", "Applied", "Apply"}:
                    self.easy_applier_component.job_apply(job)
                    self.write_to_file(job, "success")
                    logger.debug("Successfully applied to job: %s at %s", job.title, job.company)
    
            except Exception as e:
                logger.error("Unexpected error during job application for %s at %s: %s", job.title, job.company, e)
                self.write_to_file(job, "failed")
                continue
    
    
    def check_applicant_count(self, job) -> bool:
        """
        Checks the applicant count for a job and returns whether to proceed with the application.
        
        Args:
            job (Job): The job object containing title, company, and other details.
    
        Returns:
            bool: True if the applicant count meets the criteria or is not found, False otherwise.
        """
        try:
            # Find job insight elements related to applicant count
            job_insight_elements = self.driver.find_elements(By.CLASS_NAME, "job-details-jobs-unified-top-card__job-insight")
            logger.debug(f"Found {len(job_insight_elements)} job insight elements for {job.title} at {job.company}")
    
            for element in job_insight_elements:
                positive_text_element = element.find_element(By.XPATH, ".//span[contains(@class, 'tvm__text--positive')]")
                applicants_text = positive_text_element.text.strip().lower()
    
                # Check if element contains the word "applicant" and extract count
                if "applicant" in applicants_text:
                    logger.info(f"Applicants text found: {applicants_text}")
                    applicants_count = ''.join(filter(str.isdigit, applicants_text))
    
                    if applicants_count:
                        applicants_count = int(applicants_count)
                        logger.info(f"Extracted applicants count: {applicants_count}")
    
                        # Adjust count if "over" is mentioned
                        if "over" in applicants_text:
                            applicants_count += 1
                            logger.info(f"Adjusted count for 'over': {applicants_count}")
    
                        # Check if the count is within the acceptable range
                        if self.min_applicants <= applicants_count <= self.max_applicants:
                            logger.info(f"Applicants count {applicants_count} is within the threshold for {job.title} at {job.company}")
                            return True
                        else:
                            logger.info(f"Applicants count {applicants_count} is outside the threshold for {job.title} at {job.company}")
                            return False
    
            # If no valid applicants count is found, consider it as passing
            logger.warning(f"No valid applicants count found for {job.title} at {job.company}. Continuing.")
            return True
    
        except NoSuchElementException:
            logger.warning(f"Applicants count elements not found for {job.title} at {job.company}. Continuing.")
            return True
        except ValueError as e:
            logger.error(f"Error parsing applicants count for {job.title} at {job.company}: {e}")
            return True
        except Exception as e:
            logger.error(f"Unexpected error during applicant count check for {job.title} at {job.company}: {e}")
            return True
                
                

    def write_to_file(self, job, file_name, applicants_count=None):
        logger.debug("Writing job application result to file: %s", file_name)
        pdf_path = Path(job.pdf_path).resolve()
        pdf_path = pdf_path.as_uri()
        data = {
            "company": job.company,
            "job_title": job.title,
            "link": job.link,
            "job_recruiter": job.recruiter_link,
            "job_location": job.location,
            "pdf_path": pdf_path
        }

        if applicants_count is not None:
            data["applicants_count"] = applicants_count

        file_path = self.output_file_directory / f"{file_name}.json"
        temp_file_path = file_path.with_suffix('.tmp')

        if not file_path.exists():
            try:
                with open(temp_file_path, 'w', encoding='utf-8') as f:
                    json.dump([data], f, indent=4)
                temp_file_path.rename(file_path)
                logger.debug("Job data written to new file: %s", file_path)
            except Exception as e:
                logger.error(f"Failed to write new data to file {file_path}: {e}")
        else:
            try:
                with open(file_path, 'r+', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                    except json.JSONDecodeError:
                        logger.error("JSON decode error in file: %s. Creating a backup.", file_path)
                        file_path.rename(file_path.with_suffix('.bak'))
                        existing_data = []

                    existing_data.append(data)
                    f.seek(0)
                    json.dump(existing_data, f, indent=4)
                    f.truncate()
                    logger.debug("Job data appended to existing file: %s", file_path)
            except Exception as e:
                logger.error(f"Failed to append data to file {file_path}: {e}")

    def get_base_search_url(self, parameters):
        logger.debug("Constructing base search URL")
        url_parts = []
        if parameters['remote']:
            url_parts.append("f_CF=f_WRA")
        experience_levels = [str(i + 1) for i, (level, v) in enumerate(parameters.get('experience_level', {}).items())
                             if
                             v]
        if experience_levels:
            url_parts.append(f"f_E={','.join(experience_levels)}")
        url_parts.append(f"distance={parameters['distance']}")
        job_types = [key[0].upper() for key, value in parameters.get('jobTypes', {}).items() if value]
        if job_types:
            url_parts.append(f"f_JT={','.join(job_types)}")
        date_mapping = {
            "all time": "",
            "month": "&f_TPR=r2592000",
            "week": "&f_TPR=r604800",
            "24 hours": "&f_TPR=r86400"
        }
        date_param = next((v for k, v in date_mapping.items() if parameters.get('date', {}).get(k)), "")

        # Easy Apply filter
        url_parts.append("f_LF=f_AL")

        # Add sortBy parameter for sorting by date
        sort_by = parameters.get('sort_by', 'date')  # Use 'relevant' as default
        if sort_by == 'date':
            url_parts.append("sortBy=DD")

        base_url = "&".join(url_parts)
        full_url = f"?{base_url}{date_param}"

        logger.debug("Base search URL constructed: %s", full_url)
        return full_url

    def next_job_page(self, position, location, job_page):
        logger.debug("Navigating to next job page: %s in %s, page %d", position, location, job_page)
        self.driver.get(
            f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}{location}&start={job_page * 25}")

    def extract_job_information_from_tile(self, job_tile):
        logger.debug("Extracting job information from tile")
        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        try:
            print(job_tile.get_attribute('outerHTML'))
            job_title = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').find_element(By.TAG_NAME, 'strong').text

            link = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').get_attribute('href').split('?')[0]
            company = job_tile.find_element(By.CLASS_NAME, 'job-card-container__primary-description').text
            logger.debug("Job information extracted: %s at %s", job_title, company)
        except NoSuchElementException:
            logger.warning("Some job information (title, link, or company) is missing.")
        try:
            job_location = job_tile.find_element(By.CLASS_NAME, 'job-card-container__metadata-item').text
        except NoSuchElementException:
            logger.warning("Job location is missing.")
        try:
            apply_method = job_tile.find_element(By.CLASS_NAME, 'job-card-container__apply-method').text
        except NoSuchElementException:
            apply_method = "Applied"
            logger.warning("Apply method not found, assuming 'Applied'.")

        return job_title, company, job_location, link, apply_method

    def is_blacklisted(self, job_title, company, link):
        logger.debug(f"Checking if job is blacklisted: {job_title} at {company}")

        job_title_lower = job_title.lower()
        company_lower = company.strip().lower()

        # Проверка на пустой список blacklist
        if not self.title_blacklist:
            return False

        # Создаем регулярное выражение с учетом границ слова
        blacklist_pattern = r'\b(' + '|'.join(re.escape(phrase.lower()) for phrase in self.title_blacklist) + r')\b'

        # Проверяем, есть ли совпадения в заголовке вакансии
        title_blacklisted = bool(re.search(blacklist_pattern, job_title_lower))
        logger.debug(f"Title blacklist status: {title_blacklisted}")

        # Проверка компании
        company_blacklisted = company_lower in (word.strip().lower() for word in self.company_blacklist)
        logger.debug(f"Company blacklist status: {company_blacklisted}")

        # Проверка ссылки
        link_seen = link in self.seen_jobs
        logger.debug(f"Link seen status: {link_seen}")

        is_blacklisted = title_blacklisted or company_blacklisted or link_seen
        logger.debug(f"Job blacklisted status: {is_blacklisted}")

        return is_blacklisted

    def is_already_applied_to_job(self, job_title, company, link):
        link_seen = link in self.seen_jobs
        if link_seen:
            logger.debug(f"Already applied to job: {job_title} at {company}, skipping...")
        return link_seen

    def is_already_applied_to_company(self, company):
        if not self.apply_once_at_company:
            return False

        output_files = ["success.json"]
        for file_name in output_files:
            file_path = self.output_file_directory / file_name
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                        for applied_job in existing_data:
                            if applied_job['company'].strip().lower() == company.strip().lower():
                                logger.debug(
                                    f"Already applied at {company} (once per company policy), skipping...")
                                return True
                    except json.JSONDecodeError:
                        continue
        return False
