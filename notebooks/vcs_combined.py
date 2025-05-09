import pandas as pd
import numpy as np
import os

def process_vcs_data(projects_file='registered_vcs.csv', issuances_file='vcus.csv', 
                     output_file='vcs_projects_for_analysis.csv'):
    """
    Process VCS project and issuance data to create a merged analysis dataset.
    """
    print(f"Starting data processing for VCS projects analysis...")
    
    # Load the data
    df_projects = pd.read_csv(projects_file)
    df_issuances = pd.read_csv(issuances_file, low_memory=False)
    
    print(f"Loaded {len(df_projects)} unique projects from {projects_file}")
    print(f"Loaded {len(df_issuances)} issuance records from {issuances_file}")
    
    # CRITICAL FIX: Explicitly use the correct ID columns
    project_id_col = 'ID'
    issuance_id_col = 'ID'  # Column 4 in the issuances file
    
    print(f"Using '{project_id_col}' as project ID in projects data")
    print(f"Using '{issuance_id_col}' as project ID in issuances data")
    
    # Convert date columns in projects data
    date_cols_projects = ['Project Registration Date', 'Crediting Period Start Date', 'Crediting Period End Date']
    for col in date_cols_projects:
        df_projects[col] = pd.to_datetime(df_projects[col], errors='coerce')
    
    # Convert date columns in issuances data
    date_cols_issuances = ['Issuance Date', 'Vintage Start', 'Vintage End', 'Retirement/Cancellation Date']
    for col in date_cols_issuances:
        if col in df_issuances.columns:
            # Handle dates in format DD-MM-YY
            df_issuances[col] = pd.to_datetime(df_issuances[col], errors='coerce', dayfirst=True)
    
    # Convert numeric columns
    df_projects['Estimated Annual Emission Reductions'] = pd.to_numeric(
        df_projects['Estimated Annual Emission Reductions'].astype(str).str.replace(',', ''), 
        errors='coerce'
    ).fillna(0)
    
    df_issuances['Quantity Issued'] = pd.to_numeric(
        df_issuances['Quantity Issued'].astype(str).str.replace(',', ''), 
        errors='coerce'
    ).fillna(0)
    
    # Clean ID columns
    df_projects[project_id_col] = df_projects[project_id_col].astype(str).str.strip()
    df_issuances[issuance_id_col] = df_issuances[issuance_id_col].astype(str).str.strip()
    
    # Aggregate issuances by project ID
    print("Aggregating issuance data by project ID...")
    df_issuances_aggregated = df_issuances.groupby(issuance_id_col).agg({
        'Quantity Issued': 'sum',  # Total VCUs issued
        'Vintage Start': 'min',  # Earliest vintage start date
        'Vintage End': 'max'  # Latest vintage end date
    }).reset_index()
    
    # Rename columns for clarity
    df_issuances_aggregated.rename(columns={
        'Quantity Issued': 'Total_Actual_VCUs_Issued',
        'Vintage Start': 'Actual_Issuance_Start_Date',
        'Vintage End': 'Actual_Issuance_End_Date'
    }, inplace=True)
    
    print(f"Aggregated issuance data for {len(df_issuances_aggregated)} projects")
    
    # Check overlap between datasets
    projects_ids = set(df_projects[project_id_col])
    issuances_ids = set(df_issuances_aggregated[issuance_id_col])
    common_ids = projects_ids.intersection(issuances_ids)
    
    print(f"Number of unique project IDs in projects data: {len(projects_ids)}")
    print(f"Number of unique project IDs in issuances data: {len(issuances_ids)}")
    print(f"Number of common IDs between datasets: {len(common_ids)}")
    
    # Merge project data with aggregated issuance data
    df_merged = pd.merge(
        df_projects, 
        df_issuances_aggregated, 
        left_on=project_id_col, 
        right_on=issuance_id_col, 
        how='left'
    )
    
    print(f"Merged data has {len(df_merged)} rows")
    print(f"Projects with issuance data: {df_merged['Total_Actual_VCUs_Issued'].notna().sum()}")
    
    # Calculate analysis variables
    # t_actual_days = days between start and end dates
    df_merged['t_actual_days'] = (df_merged['Actual_Issuance_End_Date'] - 
                                  df_merged['Actual_Issuance_Start_Date']).dt.days
    
    # Handle cases where dates are the same or missing
    df_merged['t_actual_days'] = df_merged['t_actual_days'].fillna(0)
    
    # Convert to years
    df_merged['t_actual_years'] = df_merged['t_actual_days'] / 365.25
    
    # Calculate Total_Estimated_ERs_Actual_Period
    df_merged['Total_Estimated_ERs_Actual_Period'] = df_merged['Estimated Annual Emission Reductions'] * df_merged['t_actual_years']
    
    # Calculate q_quotient
    df_merged['q_quotient'] = np.where(
        df_merged['Total_Estimated_ERs_Actual_Period'] > 0,
        df_merged['Total_Actual_VCUs_Issued'] / df_merged['Total_Estimated_ERs_Actual_Period'],
        np.nan
    )
    
    # Calculate log_q_success_indicator
    df_merged['log_q_success_indicator'] = np.where(
        df_merged['q_quotient'] > 0,
        np.log(df_merged['q_quotient']),
        np.nan
    )
    
    # Filter for analysis
    has_vcus = df_merged['Total_Actual_VCUs_Issued'].notna() & (df_merged['Total_Actual_VCUs_Issued'] > 0)
    valid_years = df_merged['t_actual_years'] > 0
    valid_log_q = df_merged['log_q_success_indicator'].notna()
    
    # Combine the filters
    analysis_filter = has_vcus & valid_years & valid_log_q
    
    df_filtered = df_merged[analysis_filter].copy()
    
    print(f"Final filtered dataset has {len(df_filtered)} projects (from original {len(df_projects)})")
    
    # Save output
    df_filtered.to_csv(output_file, index=False)
    print(f"Successfully saved {len(df_filtered)} rows to {output_file}")
    
    # Print summary statistics
    print("\nSummary Statistics:")
    print(f"Number of unique projects in original dataset: {len(df_projects)}")
    print(f"Number of unique projects with issuances: {df_merged['Total_Actual_VCUs_Issued'].notna().sum()}")
    print(f"Number of projects remaining after final filtering: {len(df_filtered)}")
    
    return df_filtered

if __name__ == "__main__":
    # Execute the processing function
    try:
        result_df = process_vcs_data()
        print("Processing completed successfully!")
    except Exception as e:
        print(f"Processing failed with error: {str(e)}")