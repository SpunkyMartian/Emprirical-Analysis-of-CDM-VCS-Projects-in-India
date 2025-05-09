#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UNFCCC CDM Project Data Scraper (Form Submission)

This script properly submits the search form on the UNFCCC CDM website
to retrieve Indian projects with 'Registered' status, then scrapes the
results table and project detail pages.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import logging
import random
import sys
import os
import traceback
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cdm_form_scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

# Constants
BASE_URL = "https://cdm.unfccc.int"
SEARCH_URL = f"{BASE_URL}/Projects/projsearch.html"
PROJECT_URL = f"{BASE_URL}/Projects/DB"
OUTPUT_FILE = "cdm_india_projects_data.csv"

# Request headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def get_page(url, params=None, method="GET", data=None):
    """
    Fetch a web page with error handling
    
    Args:
        url: URL to fetch
        params: Optional query parameters for GET requests
        method: HTTP method (GET or POST)
        data: Optional form data for POST requests
        
    Returns:
        BeautifulSoup object or None if failed
    """
    try:
        # Add a delay to be nice to the server
        time.sleep(random.uniform(2, 4))
        
        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        else:  # POST
            response = requests.post(url, params=params, data=data, headers=HEADERS, timeout=30)
        
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except Exception as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        print(f"Error fetching {url}: {str(e)}")
        traceback.print_exc()
        return None

def submit_search_form():
    """
    Submit the search form with the proper parameters to get Indian registered projects
    
    Returns:
        BeautifulSoup object of the results page or None if failed
    """
    print("Submitting search form...")
    
    # Form data based on the form in the screenshot
    form_data = {
        'SubmitAction': 'search',
        'Title': '',  # Leave title empty to get all projects
        'sc': 'any',  # Sectoral Scopes: any
        'scale': 'All',  # Scale: All
        'method': 'any',  # Methodologies: any
        'country': 'IN',  # Host Country: India (IN is the country code)
        'other_country': '',  # No other countries filter
        'status': 'Registered',  # Status: Registered
        'reg_from': '',  # No date range filter
        'reg_to': ''
    }
    
    # Log the form data we're submitting
    print(f"Form data: {form_data}")
    
    # Submit the form
    soup = get_page(SEARCH_URL, method="POST", data=form_data)
    
    if soup:
        # Save the response for inspection
        with open("search_results.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("Saved search results to search_results.html")
    
    return soup

def extract_projects_from_table(soup):
    """
    Extract project data from the results table
    
    Args:
        soup: BeautifulSoup object of the results page
        
    Returns:
        List of dictionaries containing project data
    """
    projects = []
    
    # Check if we have search results
    total_projects_elem = soup.find(string=re.compile(r'Total projects found:'))
    if total_projects_elem:
        total_match = re.search(r'Total projects found:\s*(\d+)', total_projects_elem)
        if total_match:
            total_projects = int(total_match.group(1))
            print(f"Total projects found: {total_projects}")
            if total_projects == 0:
                print("No projects found in search results")
                return projects
    
    # Find the results table with the appropriate headers
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables on the page")
    
    results_table = None
    for i, table in enumerate(tables):
        headers = table.find_all('th')
        header_texts = [h.get_text(strip=True) for h in headers]
        print(f"Table {i+1} headers: {header_texts}")
        
        # Check if this is the results table (should have Registered, Title, etc. headers)
        if 'Registered' in header_texts and 'Title' in header_texts and 'Host Parties' in header_texts:
            results_table = table
            print(f"Found project results table (#{i+1})")
            break
    
    if not results_table:
        print("No results table found on the page")
        return projects
    
    # Extract project rows (skip header row)
    rows = results_table.find_all('tr')[1:]  # Skip header row
    print(f"Found {len(rows)} project rows")
    
    # Process each row
    for idx, row in enumerate(rows):
        try:
            cells = row.find_all('td')
            if len(cells) < 7:
                print(f"Row {idx+1} has insufficient cells ({len(cells)}), skipping")
                continue
            
            # Extract data based on cell position
            project_data = {
                'Registered': cells[0].get_text(strip=True),
                'Title': cells[1].get_text(strip=True),
                'Host_Parties': cells[2].get_text(strip=True),
                'Other_Parties': cells[3].get_text(strip=True),
                'Methodology': cells[4].get_text(strip=True),
                'Reductions': cells[5].get_text(strip=True),
                'Ref': cells[6].get_text(strip=True)
            }
            
            # Extract Project ID from the detail link
            if cells[1].find('a'):
                detail_link = cells[1].find('a').get('href')
                project_data['Detail_Link'] = detail_link
                
                if detail_link:
                    # Example: https://cdm.unfccc.int/Projects/DB/DNV-CUK1182246827.3/view
                    match = re.search(r'/Projects/DB/([\w\-\.]+)/view', detail_link)
                    if match:
                        project_data['Project_ID'] = match.group(1)
                        print(f"Extracted Project ID: {match.group(1)} for project {project_data['Ref']}")
            
            projects.append(project_data)
            
            # Print progress periodically
            if idx == 0 or (idx+1) % 10 == 0 or idx == len(rows) - 1:
                print(f"Processed {idx+1}/{len(rows)} projects")
                
        except Exception as e:
            print(f"Error processing row {idx+1}: {str(e)}")
            traceback.print_exc()
    
    return projects

def scrape_project_details(project_id, ref_no):
    """
    Scrape detailed project information
    
    Args:
        project_id: Project ID
        ref_no: Reference number
        
    Returns:
        Dictionary of detailed project information
    """
    url = f"{PROJECT_URL}/{project_id}/view"
    print(f"Scraping details for project {ref_no} ({url})")
    
    soup = get_page(url)
    if not soup:
        print(f"Failed to retrieve details for project {ref_no}")
        return {}
    
    # Save the HTML for inspection
    detail_dir = "project_details"
    os.makedirs(detail_dir, exist_ok=True)
    with open(f"{detail_dir}/project_{ref_no}.html", "w", encoding="utf-8") as f:
        f.write(soup.prettify())
    
    # Extract project details
    details = {}
    
    # Function to extract field by label
    def get_field(label):
        try:
            th = soup.find('th', string=re.compile(label, re.IGNORECASE))
            if th:
                td = th.find_next('td')
                if td:
                    return td.get_text(strip=True)
        except Exception as e:
            print(f"Error extracting {label}: {str(e)}")
        return None
    
    # Extract key fields
    details['Detail_Scale'] = get_field('Scale')
    details['Detail_Registration_Date'] = get_field('Registered')
    details['Detail_Crediting_Period'] = get_field('Crediting period')
    details['Detail_Sectoral_Scopes'] = get_field('Sectoral scopes')
    
    # Extract issuance information
    issuance_th = soup.find('th', string=re.compile('Requests for Issuance', re.IGNORECASE))
    if issuance_th:
        issuance_td = issuance_th.find_next('td')
        if issuance_td:
            issuance_text = issuance_td.get_text(strip=True)
            details['Has_Issuance'] = 'Yes' if issuance_text else 'No'
    
    return details

def main():
    print("\n" + "="*80)
    print(" "*25 + "CDM FORM SUBMISSION SCRAPER")
    print("="*80 + "\n")
    
    logger.info("Starting CDM Form Submission Scraper")
    
    try:
        # Step 1: Submit search form
        results_soup = submit_search_form()
        if not results_soup:
            print("Failed to submit search form. Exiting.")
            return
        
        # Step 2: Extract projects from results table
        projects = extract_projects_from_table(results_soup)
        if not projects:
            print("No projects found in search results. Exiting.")
            return
        
        print(f"Extracted {len(projects)} projects from search results")
        
        # Save initial results as checkpoint
        pd.DataFrame(projects).to_csv("search_results.csv", index=False, encoding="utf-8")
        print("Saved search results to search_results.csv")
        
        # Step 3: Scrape project details (limit to first 5 for testing)
        projects_to_process = projects[:5] if len(projects) > 5 else projects
        print(f"Will process {len(projects_to_process)} projects for detailed information")
        
        for idx, project in enumerate(projects_to_process):
            if 'Project_ID' in project:
                print(f"\nProcessing project {idx+1}/{len(projects_to_process)}: {project['Ref']}")
                details = scrape_project_details(project['Project_ID'], project['Ref'])
                
                # Add details to the project data
                projects[idx].update(details)
                
                # Add a delay between requests
                if idx < len(projects_to_process) - 1:
                    delay = random.uniform(3, 6)
                    print(f"Waiting {delay:.2f} seconds before next request...")
                    time.sleep(delay)
        
        # Step 4: Save final results
        final_df = pd.DataFrame(projects)
        final_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
        print(f"\nSaved {len(projects)} projects to {OUTPUT_FILE}")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()
    
    print("\n" + "="*80)
    print(" "*30 + "SCRAPING COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()