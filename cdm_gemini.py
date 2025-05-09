import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import pandas as pd
import time
import re
from datetime import datetime
import logging
import random

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager # To auto-manage chromedriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions


# --- Configuration ---
BASE_URL = "https://cdm.unfccc.int"
# Initial search URL (without page parameter for Selenium)
SEARCH_URL_START = BASE_URL + "/Projects/projsearch.html?hp=IN" # Filter for India
PROJECT_PAGE_URL_TEMPLATE = BASE_URL + "/Projects/DB/Project_Information/Project?RefNo={ref_no}"
OUTPUT_CSV_FILE = "cdm_india_projects_data_selenium.csv"
REQUEST_DELAY_SECONDS = 1.5 # Can potentially be lower with Selenium, but keep some delay
MAX_RETRIES = 3 # For stage 2 requests

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions (Requests based, for Stage 2) ---
def safe_get_text(element, strip=True, default=""):
    """Safely extracts text from a BeautifulSoup element OR Selenium WebElement."""
    if hasattr(element, 'text'): # Selenium WebElement
        try:
            text = element.text
            return text.strip() if strip else text
        except StaleElementReferenceException:
            logging.warning("StaleElementReferenceException encountered in safe_get_text")
            return default
        except Exception as e:
            logging.warning(f"Exception in safe_get_text (Selenium): {e}")
            return default
    elif element: # BeautifulSoup element
        return element.get_text(strip=strip) if element else default
    return default

def make_request(url):
    """Makes a GET request with retries and delay (Used for Stage 2)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(random.uniform(REQUEST_DELAY_SECONDS, REQUEST_DELAY_SECONDS + 1))
            response = requests.get(url, timeout=45, headers=headers)
            response.raise_for_status()
            if "An error has occurred" in response.text or "Invalid Request" in response.text:
                 logging.warning(f"Server returned an error page for {url} (Attempt {attempt+1}/{MAX_RETRIES}).")
                 raise requests.exceptions.RequestException("Server error page detected")
            return response
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request failed for {url} (Attempt {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt == MAX_RETRIES - 1:
                logging.error(f"Max retries reached for {url}. Skipping.")
                return None
            time.sleep(6 * (attempt + 1))
    return None

# --- Stage 1: Scrape Search Results using Selenium ---
def scrape_search_results_selenium():
    """Scrapes project listings using Selenium to handle JavaScript pagination."""
    all_projects_summary = []
    logging.info("Starting Stage 1: Scraping search results using Selenium...")

    # --- Selenium WebDriver Setup ---
    chrome_options = ChromeOptions()
    # chrome_options.add_argument("--headless")  # Run in background without opening a browser window
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Use webdriver-manager to handle driver installation/update
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("ChromeDriver initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize ChromeDriver: {e}")
        logging.error("Please ensure Chrome is installed and webdriver-manager can access the internet.")
        return pd.DataFrame() # Return empty if driver fails

    current_page = 1
    max_pages_to_try = 70 # Set a reasonable max based on observed pages (e.g., 57)

    try:
        driver.get(SEARCH_URL_START)
        logging.info(f"Opened initial search page: {SEARCH_URL_START}")
        wait = WebDriverWait(driver, 20) # Wait up to 20 seconds for elements

        while current_page <= max_pages_to_try:
            logging.info(f"Processing page {current_page}...")

            try:
                # Wait for the table and pagination to be potentially updated
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.proj_table")))
                wait.until(EC.presence_of_element_located((By.ID, "projectsPages")))
                # Add a small explicit wait to ensure JS rendering finishes after AJAX call (if any)
                time.sleep(random.uniform(1.5, 2.5))

                # Get page source *after* potential JS updates
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'lxml')
                table = soup.find('table', class_='proj_table')

                if not table:
                    logging.warning(f"No project table found on page {current_page} source. Stopping.")
                    break

                header_row = table.find('tr')
                if not header_row or not header_row.find_all('th'):
                    logging.warning(f"Could not find valid header row on page {current_page}. Stopping.")
                    break
                data_rows = header_row.find_next_siblings('tr')

                if not data_rows:
                    logging.info(f"No data rows found on page {current_page}. Likely end of results.")
                    break

                page_has_valid_data = False
                current_page_refs = set() # Track refs found on this specific page load
                for row in data_rows:
                    cells = row.find_all('td', recursive=False)
                    if len(cells) >= 7:
                        try:
                            ref_no = safe_get_text(cells[6]).strip()
                            title_link = cells[1].find('a')
                            title_search = safe_get_text(title_link) if title_link else safe_get_text(cells[1])

                            if not ref_no or not title_search:
                                logging.debug(f"Skipping row on page {current_page}, missing Ref or Title.")
                                continue

                            # Prevent adding duplicates scraped from the *same* page load if JS is slow
                            if ref_no in current_page_refs:
                                continue
                            current_page_refs.add(ref_no)

                            page_has_valid_data = True
                            project_data = {
                                'Ref': ref_no,
                                'Registered_Search': safe_get_text(cells[0]),
                                'Title_Search': title_search,
                                'Host_Parties_Search': safe_get_text(cells[2]),
                                'Other_Parties_Raw_Search': ' ; '.join(span.get_text(strip=True) for span in cells[3].find_all('span')) if cells[3] else '',
                                'Methodology_Search': safe_get_text(cells[4]),
                                'Est_Reductions_Search': safe_get_text(cells[5]),
                            }
                            all_projects_summary.append(project_data)
                        except Exception as e:
                            logging.error(f"Error processing row on page {current_page}: {e}")
                    else:
                         logging.debug(f"Skipping row on page {current_page} due to insufficient columns ({len(cells)}).")

                if not page_has_valid_data and data_rows:
                     logging.info(f"Processed page {current_page} but found no valid data rows. Assuming end.")
                     break # Stop if page has rows but none yield data

                # --- Selenium Pagination Click ---
                next_page = current_page + 1
                if next_page > max_pages_to_try:
                    logging.info("Reached max pages to try limit.")
                    break

                try:
                    # Find the link for the *next* page number
                    pagination_div = wait.until(EC.visibility_of_element_located((By.ID, "projectsPages")))
                    # Use XPath to find the link by its exact text content
                    next_page_link = pagination_div.find_element(By.XPATH, f".//a[normalize-space()='{next_page}']")
                    logging.info(f"Found link for page {next_page}. Clicking...")
                    # Scroll into view and click using JavaScript to avoid interception issues
                    driver.execute_script("arguments[0].scrollIntoView(true);", next_page_link)
                    time.sleep(0.5) # Short pause before click
                    driver.execute_script("arguments[0].click();", next_page_link)
                    current_page = next_page # Update current page number *after* successful click simulation

                except NoSuchElementException:
                    logging.info(f"No link found for page {next_page}. Reached the last page.")
                    break # No more pages
                except TimeoutException:
                     logging.warning(f"Timed out waiting for pagination element on page {current_page} before trying to click next. Stopping.")
                     break
                except Exception as click_err:
                     logging.error(f"Error clicking next page link ({next_page}): {click_err}. Stopping.")
                     break # Stop if clicking fails

            except TimeoutException:
                logging.warning(f"Timed out waiting for table/pagination on page {current_page}. Assuming end or error.")
                break
            except Exception as page_err:
                logging.error(f"Unexpected error processing page {current_page}: {page_err}")
                break # Stop on unexpected errors


    except Exception as e:
        logging.error(f"An error occurred during Selenium execution: {e}")
    finally:
        if 'driver' in locals() and driver:
            driver.quit() # Ensure browser closes even on error
            logging.info("WebDriver closed.")

    logging.info(f"Finished Stage 1: Scraped {len(all_projects_summary)} project summaries.")
    if not all_projects_summary:
        return pd.DataFrame()
    # Remove duplicates that might have been scraped across page loads before returning
    summary_df = pd.DataFrame(all_projects_summary)
    summary_df.drop_duplicates(subset=['Ref'], keep='first', inplace=True)
    logging.info(f"Returning {len(summary_df)} unique project summaries after deduplication.")
    return summary_df


# --- Stage 2: Scrape Individual Project Pages (Using Requests) ---
# (Function scrape_project_details remains largely the same as the previous version
#  as it uses direct URL access via requests, which is fine for detail pages)
def scrape_project_details(ref_no):
    """Scrapes detailed information from a single project page, including all issuance details."""
    project_url = PROJECT_PAGE_URL_TEMPLATE.format(ref_no=ref_no)
    logging.debug(f"Scraping details for Ref: {ref_no} ({project_url})")
    response = make_request(project_url)
    if not response:
        return {'Ref': ref_no, 'Scrape_Status': 'Failed Fetch'}

    soup = BeautifulSoup(response.content, 'lxml')
    details = {'Ref': ref_no, 'Scrape_Status': 'Success'}

    try:
        # Find data using labels (<th> followed by <td>)
        data_map = {}
        all_th = soup.select('tbody > tr > th')
        for th in all_th:
            label_text = ' '.join(safe_get_text(th).split())
            value_td = th.find_next_sibling('td')
            if value_td:
                data_map[label_text] = value_td

        # Extract general project fields
        details['Proj_Title_Detail'] = safe_get_text(data_map.get('Project title').find('span')) if data_map.get('Project title') else None

        # Other Parties Involved
        other_parties_td = data_map.get('Other Parties Involved')
        other_countries = []
        if other_parties_td:
             strong_tags = other_parties_td.find_all('strong')
             for tag in strong_tags:
                 country_name = safe_get_text(tag)
                 if country_name.lower() != 'india':
                     other_countries.append(country_name)
        details['Other_Countries_Detail'] = " ; ".join(sorted(list(set(other_countries))))
        details['Num_Other_Countries_Detail'] = len(set(other_countries))

        details['Sectoral_Scopes_Detail'] = safe_get_text(data_map.get('Sectoral scopes'))
        details['Scale_Detail'] = safe_get_text(data_map.get('Activity Scale'))

        # Methodologies Used
        methodology_td = data_map.get('Methodologies Used')
        methodologies = []
        if methodology_td:
            links = methodology_td.select('span > a') or methodology_td.find_all('a')
            for link in links:
                methodologies.append(safe_get_text(link))
        details['Methodologies_Detail'] = " ; ".join(methodologies)

        # Amount of Reductions (Estimated Annual ERs)
        er_td = data_map.get('Amount of Reductions')
        details['Est_Annual_ERs_Raw_Detail'] = safe_get_text(er_td) if er_td else None
        er_numeric = None
        if details['Est_Annual_ERs_Raw_Detail']:
            er_match = re.search(r'([\d,]+)\s*metric tonnes CO2', details['Est_Annual_ERs_Raw_Detail'], re.IGNORECASE)
            if er_match:
                try: er_numeric = int(er_match.group(1).replace(',', ''))
                except ValueError: logging.warning(f"Ref {ref_no}: Could not convert Est Annual ER value '{er_match.group(1)}' to int.")
        details['Est_Annual_ERs_Numeric_Detail'] = er_numeric

        # Registration Date
        reg_date_td = data_map.get('Registration Date')
        details['Registered_Date_Detail'] = safe_get_text(reg_date_td.find('span')) if reg_date_td else None

        # Planned Crediting Period
        cp_td = data_map.get('Crediting Period')
        planned_cp_text = ""
        if cp_td:
            planned_cp_text = ''.join(t for t in cp_td.contents if isinstance(t, NavigableString)).strip()
            if not planned_cp_text: planned_cp_text = cp_td.get_text(separator=' ', strip=True).split('Changed from:')[0].strip()
        details['Planned_CP_Raw_Detail'] = planned_cp_text


        # Extract ALL Issuance Data
        issuance_periods_str_list = []
        issuance_cer_amounts_str_list = []
        issuance_statuses_str_list = []
        issuance_td = data_map.get('Requests for Issuance and related documentation')

        if issuance_td:
            # Split content by <hr> tags to isolate issuance blocks
            content_parts = []
            current_part = ""
            for content in issuance_td.contents:
                 if isinstance(content, Tag) and content.name == 'hr':
                     if current_part.strip(): content_parts.append(current_part)
                     current_part = ""
                 else: current_part += str(content)
            if current_part.strip(): content_parts.append(current_part)

            for block_html in content_parts:
                block_soup = BeautifulSoup(block_html, 'lxml')
                block_text = block_soup.get_text(" ", strip=True)

                # Extract Monitoring Period
                mp_str = None
                mp_match = re.search(r'Monitoring report.*?:.*?(\d{1,2}\s+\w{3}\s+\d{2,4})\s*-\s*(\d{1,2}\s+\w{3}\s+\d{2,4})', block_text, re.IGNORECASE)
                if mp_match: mp_str = f"{mp_match.group(1)} - {mp_match.group(2)}"
                issuance_periods_str_list.append(mp_str if mp_str else '')

                # Extract CER Amount
                cer_str = None
                cer_match = re.search(r'CERs requested (?:up to.*?|from.*?):\s*([\d,]+)', block_text, re.IGNORECASE)
                if cer_match: cer_str = cer_match.group(1)
                issuance_cer_amounts_str_list.append(cer_str if cer_str else '')

                # Extract Status
                status_str = None
                status_match = re.search(r'Issuance request state:\s*(.+?)(?:\s*<br|\s*\n|\s*$)', block_html, re.IGNORECASE | re.DOTALL)
                if status_match:
                    status_str = BeautifulSoup(status_match.group(1).strip(), 'lxml').get_text(strip=True)
                else: # Fallback text checks
                    if "Issuance request state: Issued" in block_text: status_str = "Issued"
                    elif "Issuance request state: Pending" in block_text: status_str = "Pending"
                    elif "Issuance request state: Withdrawn" in block_text: status_str = "Withdrawn"
                    elif "Issuance request state: Rejected" in block_text: status_str = "Rejected"
                issuance_statuses_str_list.append(status_str if status_str else '')

        details['Issuance_Periods_List_Str'] = " ; ".join(issuance_periods_str_list)
        details['Issuance_CERs_List_Str'] = " ; ".join(issuance_cer_amounts_str_list)
        details['Issuance_Statuses_List_Str'] = " ; ".join(issuance_statuses_str_list)

        return details

    except Exception as e:
        logging.exception(f"Critical error scraping details for Ref {ref_no}: {e}")
        details['Scrape_Status'] = f'Failed Detail Scrape: {e}'
        return details

# --- Main Execution ---
if __name__ == "__main__":
    # Stage 1 using Selenium
    search_results_df = scrape_search_results_selenium() # Use the Selenium function

    if search_results_df.empty:
        logging.error("No project summaries were scraped from search results (Selenium Stage 1). Exiting.")
    else:
        # Ensure Ref is clean string for merging
        search_results_df['Ref'] = search_results_df['Ref'].astype(str).str.strip()
        # Deduplication already happened within scrape_search_results_selenium

        # Stage 2 using Requests (as before)
        all_details = []
        unique_refs = search_results_df['Ref'].unique()
        total_projects = len(unique_refs)
        logging.info(f"Starting Stage 2: Scraping details for {total_projects} unique projects using Requests...")

        for i, ref_no in enumerate(unique_refs):
            if not ref_no or not re.match(r'^\d+$', ref_no):
                logging.warning(f"Skipping invalid Ref format: '{ref_no}' at index {i}")
                continue
            logging.info(f"Processing project {i+1}/{total_projects} (Ref: {ref_no})...")
            details = scrape_project_details(ref_no)
            if details is None:
                details = {'Ref': ref_no, 'Scrape_Status': 'Complete Failure in scrape_project_details'}
            all_details.append(details)

        logging.info(f"Finished Stage 2: Processed {len(all_details)} projects.")

        if not all_details:
             logging.error("No details were scraped in Stage 2. Check logs. Exiting.")
        else:
            details_df = pd.DataFrame(all_details)
            details_df['Ref'] = details_df['Ref'].astype(str).str.strip()

            # Stage 3: Merge Data
            logging.info("Merging search results with detailed data...")
            if 'Ref' not in search_results_df.columns or search_results_df['Ref'].isnull().any():
                logging.error("FATAL: 'Ref' column missing or contains nulls in search results DataFrame.")
            elif 'Ref' not in details_df.columns or details_df['Ref'].isnull().any():
                 logging.error("FATAL: 'Ref' column missing or contains nulls in details DataFrame.")
            else:
                final_df = pd.merge(search_results_df, details_df, on='Ref', how='left')

                # Final Column Selection and Renaming
                final_columns = {
                    'Ref': 'Ref', 'Registered_Search': 'Registered_Date_Search', 'Title_Search': 'Title_Search',
                    'Host_Parties_Search': 'Host_Parties_Search', 'Other_Parties_Raw_Search': 'Other_Parties_Raw_Search',
                    'Methodology_Search': 'Methodology_Search', 'Est_Reductions_Search': 'Est_Reductions_Search',
                    'Scrape_Status': 'Scrape_Status', 'Proj_Title_Detail': 'Title_Detail',
                    'Other_Countries_Detail': 'Other_Countries_Detail', 'Num_Other_Countries_Detail': 'Num_Other_Countries_Detail',
                    'Sectoral_Scopes_Detail': 'Sectoral_Scopes_Detail', 'Scale_Detail': 'Scale_Detail',
                    'Methodologies_Detail': 'Methodologies_Detail', 'Est_Annual_ERs_Raw_Detail': 'Est_Annual_ERs_Raw_Detail',
                    'Est_Annual_ERs_Numeric_Detail': 'Est_Annual_ERs_Numeric_Detail', 'Registered_Date_Detail': 'Registered_Date_Detail',
                    'Planned_CP_Raw_Detail': 'Planned_CP_Raw_Detail', 'Issuance_Periods_List_Str': 'Issuance_Periods_List_Str',
                    'Issuance_CERs_List_Str': 'Issuance_CERs_List_Str', 'Issuance_Statuses_List_Str': 'Issuance_Statuses_List_Str',
                 }
                final_df_selected = final_df[[col for col in final_columns if col in final_df.columns]].rename(columns=final_columns)

                # Save final data
                try:
                    final_df_selected.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
                    logging.info(f"Successfully saved combined data ({len(final_df_selected)} rows) to {OUTPUT_CSV_FILE}")
                except Exception as e:
                    logging.error(f"Failed to save data to CSV: {e}")

    logging.info("Script finished.")