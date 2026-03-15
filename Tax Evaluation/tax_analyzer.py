# -*- coding: utf-8 -*-
"""buz-Tax-2025.ipynb

Modified to support multiple credit card files from a folder
All file paths and folder configurations are at the top for easy modification
"""

# ============================================================================
# 📁 FILE AND FOLDER CONFIGURATION
# ============================================================================

# Base path for all tax files
BASE_PATH = '.'

# Checking Account Statement
CHECKING_STATEMENT_FILE = f'{BASE_PATH}/buz-checking-statement-full.csv'

# Credit Card Statements (kept separate - DO NOT COMBINE)
buz_CREDIT_CARD_FILE = f'{BASE_PATH}/buz-CreditCard-statement-Full.csv'
personal_CREDIT_CARD_FOLDER = f'{BASE_PATH}/Monthly statement'

# Amex Card Statement
AMEX_STATEMENT_FILE = f'{BASE_PATH}/Amex_2025.csv'

# Output Files
CHECKING_ACCOUNT_SUMMARY_FILE = 'checking_account_category_summary.csv'
buz_MERCHANT_SUMMARY_FILE = 'buz_merchant_category_summary.csv'
personal_MERCHANT_SUMMARY_FILE = 'personal_merchant_category_summary.csv'
AMEX_CATEGORY_SUMMARY_FILE = 'amex_category_summary.csv'
CONSOLIDATED_SUMMARY_EXCEL_FILE = 'consolidated_expense_summary.xlsx'
CONSOLIDATED_SUMMARY_CSV_FILE = 'consolidated_expense_summary.csv'

# File Encoding
CSV_ENCODING = 'windows-1252'

# OpenAI API Key
OPENAI_API_KEY = ""

# ============================================================================
# 📚 IMPORTS
# ============================================================================

import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from openai import OpenAI

# Check if running in Google Colab
try:
    from google.colab import files
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# ============================================================================
# 🏷️ REFERENCE CATEGORIES FOR EXPENSE CLASSIFICATION
# ============================================================================

REFERENCE_CATEGORIES = [
    'Accounting Fees',
    'Advertising and Promotion',
    'Automobile Expense',
    'Bank Service Charges',
    'Computer & Internet Expense',
    'Consulting Outsource',
    'Continuing Education',
    'Depreciation Expense',
    'Discount Expense',
    'Donation',
    'Equipment Lease',
    'Gifts',
    'Insurance Expense',
    'Interest Expense',
    'Laundry & Cleaning',
    'Legal & Professional Fees',
    'Meals and Entertainment',
    'Medical Insurance',
    'Office Supplies',
    'Parking & Tolls',
    'Payroll Expenses',
    'Postage & Delivery',
    'Printing',
    'Professional Attire Expense',
    'Recruitment Expense',
    'Rent Expense',
    'Repairs and Maintenance',
    'Salary',
    'Software',
    'Telephone Expense',
    'Trade Show Expense',
    'Travel Expense',
    'Trash',
    'Uniforms',
    'Utilities'
]

# ============================================================================
# 🛠️ UTILITY FUNCTIONS
# ============================================================================

def parse_credit_card_statement(file_path, encoding=CSV_ENCODING):
    """
    Common method to parse credit card statement files.
    Finds the header row containing 'CardHolder Name' and loads the CSV.
    
    Args:
        file_path: Path to the CSV file
        encoding: File encoding
    
    Returns:
        DataFrame with parsed credit card data
    """
    print(f"📄 Processing: {os.path.basename(file_path)}")
    
    # Read the file line by line to find the header
    with open(file_path, 'r', encoding=encoding) as f:
        lines = f.readlines()

    header_row_index = -1
    for i, line in enumerate(lines):
        if 'CardHolder Name' in line:
            header_row_index = i
            break

    if header_row_index == -1:
        raise ValueError(f"Header 'CardHolder Name' not found in {file_path}")

    # Read the CSV from the identified header row
    df = pd.read_csv(file_path, encoding=encoding, skiprows=header_row_index, 
                     parse_dates=['Posting Date', 'Trans. Date'])
    
    print(f"  ✓ Loaded {len(df)} rows")
    return df


def load_multiple_credit_card_files(folder_path, encoding=CSV_ENCODING, file_type='standard'):
    """
    Load and combine multiple credit card statement files from a folder.
    
    Args:
        folder_path: Path to folder containing credit card CSV files
        encoding: File encoding
        file_type: 'standard' for BOA credit card format, 'simple' for simple CSV format
    
    Returns:
        Combined DataFrame with all credit card transactions
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        raise ValueError(f"Folder not found: {folder_path}")
    
    # Find all CSV files in the folder
    csv_files = list(folder_path.glob('*.csv'))
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {folder_path}")
    
    print(f"\n📂 Found {len(csv_files)} CSV file(s) in {folder_path}")
    print("="*70)
    
    # Parse and combine all files
    all_dataframes = []
    for csv_file in csv_files:
        try:
            if file_type == 'simple':
                # Simple CSV format (like Personal statements)
                print(f"📄 Processing: {csv_file.name}")
                df = pd.read_csv(csv_file, encoding=encoding)
                # Rename columns to match standard format for consistency
                df = df.rename(columns={
                    'Posted Date': 'Posting Date',
                    'Payee': 'Description',
                    'Amount': 'Amount'
                })
                # Filter out payments (positive amounts)
                df = df[df['Amount'] < 0]
                # Make amounts positive
                df['Amount'] = abs(df['Amount'])
                print(f"  ✓ Loaded {len(df)} rows")
            else:
                # Standard BOA credit card format
                df = parse_credit_card_statement(csv_file, encoding)
            all_dataframes.append(df)
        except Exception as e:
            print(f"  ⚠️  Error processing {csv_file.name}: {e}")
            continue
    
    if not all_dataframes:
        raise ValueError("No files were successfully parsed")
    
    # Combine all DataFrames
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    
    print("="*70)
    print(f"✅ Combined total: {len(combined_df)} rows from {len(all_dataframes)} file(s)\n")
    
    return combined_df


def categorize_expenses_with_openai(df, reference_categories, account_name="Unknown", batch_size=30):
    """
    Use OpenAI to map expense categories to reference categories with batching for large inputs
    
    Args:
        df: DataFrame with expense data (first column: category, second: amount)
        reference_categories: List of reference category names
        account_name: Name of the account for logging purposes
        batch_size: Maximum number of items per batch (default: 30)
    
    Returns:
        Dictionary with categorized expenses
    """
    # Automatically detect column names
    category_col = df.columns[0]
    amount_col = df.columns[1]
    
    # Check if we need batching
    total_items = len(df)
    if total_items <= batch_size:
        # No batching needed - process all at once
        return _categorize_batch_with_openai(df, reference_categories, account_name, batch_num=None)
    
    # Batching needed - split into smaller chunks
    print(f"   📦 Splitting {total_items} items into batches of {batch_size}...")
    
    num_batches = (total_items + batch_size - 1) // batch_size  # Ceiling division
    all_results = {}
    
    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, total_items)
        batch_df = df.iloc[start_idx:end_idx].copy()
        
        print(f"   📊 Processing batch {i+1}/{num_batches} ({len(batch_df)} items)...")
        
        batch_results = _categorize_batch_with_openai(
            batch_df, 
            reference_categories, 
            account_name, 
            batch_num=i+1
        )
        
        # Merge results
        for category, items in batch_results.items():
            if category not in all_results:
                all_results[category] = []
            all_results[category].extend(items)
    
    print(f"   ✅ Merged results from {num_batches} batches")
    return all_results


def _categorize_batch_with_openai(df, reference_categories, account_name, batch_num=None):
    """
    Internal function to categorize a single batch of expenses
    
    Args:
        df: DataFrame with expense data
        reference_categories: List of reference category names
        account_name: Name of the account
        batch_num: Batch number for logging (None if not batched)
    
    Returns:
        Dictionary with categorized expenses for this batch
    """
    # Automatically detect column names
    category_col = df.columns[0]
    amount_col = df.columns[1]

    # Prepare the expense data as a string
    expense_list = "\n".join([f"{row[category_col]} — {row[amount_col]:.2f}"
                              for _, row in df.iterrows()])

    # Create the prompt
    prompt = f"""
You are a financial categorization assistant. I have a list of expense items with their amounts,
and I need you to categorize them into the provided reference categories.

IMPORTANT RULES:
1. You MUST use ONLY the reference categories provided below - do not create new categories
2. Do NOT Duplicate Categories
3. Choose the MOST appropriate category from the list for each expense
4. Return valid JSON with NO additional text or explanation

Expense Items:
{expense_list}

Reference Categories (USE ONLY THESE - DO NOT CREATE NEW ONES):
{', '.join(reference_categories)}

Please map each expense item to the most appropriate reference category and return the result
as a JSON object where keys are the reference categories and values are lists of objects
containing 'category' and 'amount' for each expense item.

Example format:
{{
    "Travel Expense": [
        {{"category": "TRAVEL AGENCIES", "amount": 8227.99}},
        {{"category": "QATAR AIR", "amount": 3256.05}}
    ],
    "Meals and Entertainment": [
        {{"category": "EATING PLACES, RESTAURANTS", "amount": 8179.96}}
    ]
}}

CRITICAL: Use ONLY the reference categories listed above. Do not invent new category names.

Return ONLY the JSON object, no additional text.
"""

    # Log the request
    log_filename = f"openai_log_{account_name.lower().replace(' ', '_').replace('-', '_')}.txt"
    
    # Determine write mode: append for batches, overwrite for single/first batch
    write_mode = 'a' if batch_num and batch_num > 1 else 'w'
    
    with open(log_filename, write_mode, encoding='utf-8') as log_file:
        if batch_num:
            log_file.write("\n" + "="*80 + "\n")
            log_file.write(f"BATCH {batch_num} - {account_name}\n")
            log_file.write("="*80 + "\n\n")
        else:
            log_file.write("="*80 + "\n")
            log_file.write(f"OPENAI REQUEST LOG - {account_name}\n")
            log_file.write("="*80 + "\n\n")
        
        log_file.write(f"Number of expense items: {len(df)}\n\n")
        log_file.write("EXPENSE ITEMS SENT TO OPENAI:\n")
        log_file.write("-"*80 + "\n")
        log_file.write(expense_list)
        log_file.write("\n" + "-"*80 + "\n\n")
        log_file.write("FULL PROMPT:\n")
        log_file.write("-"*80 + "\n")
        log_file.write(prompt)
        log_file.write("\n" + "-"*80 + "\n\n")

    # Call OpenAI API
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful financial assistant that categorizes expenses accurately. Always return valid JSON with each category appearing only once."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )

    # Extract and parse the response
    result_text = response.choices[0].message.content.strip()

    # Log the raw response
    with open(log_filename, 'a', encoding='utf-8') as log_file:
        log_file.write("OPENAI RAW RESPONSE:\n")
        log_file.write("-"*80 + "\n")
        log_file.write(result_text)
        log_file.write("\n" + "-"*80 + "\n\n")

    # Remove markdown code blocks if present
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]
        result_text = result_text.strip()

    # Parse JSON with automatic duplicate key merging using object_pairs_hook
    # This elegant solution intercepts duplicate keys during parsing and merges them
    duplicates_found = []
    
    def merge_duplicate_keys(pairs):
        """
        Custom object_pairs_hook for json.loads() to merge duplicate keys
        When JSON has duplicate keys like:
          {"Meals": [...], "Travel": [...], "Meals": [...]}
        This merges them into:
          {"Meals": [...all items...], "Travel": [...]}
        """
        merged = {}
        for key, value in pairs:
            if key in merged:
                # Duplicate key detected!
                if key not in duplicates_found:
                    duplicates_found.append(key)
                
                # Merge the values (assumes values are lists of items)
                if isinstance(value, list) and isinstance(merged[key], list):
                    merged[key].extend(value)
                else:
                    # Fallback: convert to list if needed
                    merged[key] = value
            else:
                merged[key] = value
        return merged
    
    # Parse with duplicate merging
    try:
        categorized_data = json.loads(result_text, object_pairs_hook=merge_duplicate_keys)
    except json.JSONDecodeError as e:
        with open(log_filename, 'a', encoding='utf-8') as log_file:
            log_file.write(f"\n� JSON PARSING ERROR:\n")
            log_file.write(f"Error: {str(e)}\n")
            log_file.write(f"Line {e.lineno}, Column {e.colno}\n")
            log_file.write(f"Failed to parse OpenAI response as valid JSON.\n\n")
        raise ValueError(f"OpenAI returned invalid JSON for {account_name}: {str(e)}")
    
    # Log if we merged any duplicates
    if duplicates_found:
        with open(log_filename, 'a', encoding='utf-8') as log_file:
            log_file.write("\n⚠️  WARNING: OpenAI returned duplicate category keys!\n")
            log_file.write(f"Duplicate categories: {duplicates_found}\n")
            log_file.write("✅ Automatically merged duplicate entries to prevent data loss.\n")
            for cat in duplicates_found:
                if cat in categorized_data and isinstance(categorized_data[cat], list):
                    total = sum(item['amount'] for item in categorized_data[cat])
                    log_file.write(f"   • {cat}: {len(categorized_data[cat])} items, total ${total:,.2f}\n")
            log_file.write("\n")
        print(f"⚠️  WARNING: Merged duplicate categories: {duplicates_found}")
    
    # Validate that OpenAI only used valid reference categories
    invalid_categories = set(categorized_data.keys()) - set(reference_categories)
    if invalid_categories:
        with open(log_filename, 'a', encoding='utf-8') as log_file:
            log_file.write("\n⚠️  ERROR: OpenAI used invalid categories!\n")
            log_file.write(f"Invalid categories: {invalid_categories}\n")
            log_file.write("These expenses will be LOST in consolidation!\n\n")
        print(f"⚠️  WARNING: OpenAI used {len(invalid_categories)} invalid categories: {invalid_categories}")
    
    # Log the parsed result
    with open(log_filename, 'a', encoding='utf-8') as log_file:
        log_file.write("PARSED JSON RESULT:\n")
        log_file.write("-"*80 + "\n")
        log_file.write(json.dumps(categorized_data, indent=2))
        log_file.write("\n" + "-"*80 + "\n\n")
        
        # Log summary statistics
        total_items_sent = len(df)
        total_items_returned = sum(len(items) for items in categorized_data.values())
        log_file.write("SUMMARY:\n")
        log_file.write("-"*80 + "\n")
        log_file.write(f"Items sent to OpenAI: {total_items_sent}\n")
        log_file.write(f"Items returned by OpenAI: {total_items_returned}\n")
        log_file.write(f"Missing items: {total_items_sent - total_items_returned}\n")
        
        if total_items_sent != total_items_returned:
            log_file.write("\n⚠️  WARNING: Some items were not categorized by OpenAI!\n")
            
            # Find missing items
            sent_items = set(df[category_col].values)
            returned_items = set()
            for items in categorized_data.values():
                for item in items:
                    returned_items.add(item['category'])
            
            missing_items = sent_items - returned_items
            if missing_items:
                log_file.write("\nMISSING ITEMS:\n")
                for missing_item in missing_items:
                    amount = df[df[category_col] == missing_item][amount_col].values[0]
                    log_file.write(f"  - {missing_item} — ${amount:.2f}\n")
        
        log_file.write("="*80 + "\n")
    
    print(f"📝 OpenAI request/response logged to: {log_filename}")
    
    return categorized_data


def categorize_multiple_dataframes(dataframes_dict, reference_categories):
    """
    Process multiple DataFrames and categorize each one
    
    Args:
        dataframes_dict: Dict with DF names as keys and DataFrames as values
        reference_categories: List of reference category names
    
    Returns:
        Dictionary with categorized data for each DataFrame
    """
    all_results = {}

    for df_name, df in dataframes_dict.items():
        print(f"\n📊 Processing {df_name}...")
        categorized = categorize_expenses_with_openai(df, reference_categories, account_name=df_name)
        all_results[df_name] = categorized
        print(f"✓ {df_name} categorization complete!")

    return all_results


def create_consolidated_summary(all_results, reference_categories):
    """
    Create a consolidated summary showing totals from each DataFrame by reference category
    
    Args:
        all_results: Dictionary with categorized results for each DataFrame
        reference_categories: List of reference category names
    
    Returns:
        DataFrame with consolidated summary
    """
    df_names = list(all_results.keys())

    # Initialize dictionary to store totals
    summary_data = {'Reference Category': []}
    for df_name in df_names:
        summary_data[f'{df_name} Total'] = []

    # Process each reference category
    for ref_category in reference_categories:
        summary_data['Reference Category'].append(ref_category)

        # Get totals from each DataFrame
        for df_name in df_names:
            categorized_data = all_results[df_name]

            total = 0
            if ref_category in categorized_data and categorized_data[ref_category]:
                for item in categorized_data[ref_category]:
                    total += item['amount']

            summary_data[f'{df_name} Total'].append(total)

    # Create DataFrame
    summary_df = pd.DataFrame(summary_data)

    # Add Grand Total column
    total_columns = [col for col in summary_df.columns if col.endswith('Total')]
    summary_df['Grand Total'] = summary_df[total_columns].sum(axis=1)

    # Filter out rows where all totals are 0
    summary_df = summary_df[summary_df['Grand Total'] > 0]

    return summary_df


def format_categorized_output(categorized_data):
    """
    Format categorized expenses into readable output with totals
    
    Args:
        categorized_data: Dictionary with categorized expense data
    
    Returns:
        Formatted string output
    """
    output = []

    for category, items in categorized_data.items():
        if not items:
            continue

        output.append(f"\n{category}:")
        output.append("=" * 50)

        total = 0
        for item in items:
            category_name = item['category']
            amount = item['amount']
            output.append(f"{category_name} — ${amount:,.2f}")
            total += amount

        output.append("-" * 50)
        output.append(f"Total {category} = ${total:,.2f}")
        output.append("")

    return "\n".join(output)


def categorized_to_dataframe(categorized_data):
    """
    Convert categorized data to DataFrame
    
    Args:
        categorized_data: Dictionary with categorized expense data
    
    Returns:
        DataFrame with reference categories
    """
    rows = []
    for ref_category, items in categorized_data.items():
        for item in items:
            rows.append({
                'Reference Category': ref_category,
                'Original Category': item['category'],
                'Amount': item['amount']
            })

    return pd.DataFrame(rows)


def analyze_credit_card_expenses(df, card_name):
    """
    Analyze and print expense summaries for a credit card DataFrame
    
    Args:
        df: Credit card DataFrame
        card_name: Name of the credit card for display purposes
    """
    print(f"\n{'='*70}")
    print(f"📊 {card_name} - Expense Analysis")
    print(f"{'='*70}")
    
    # Group by Expense Category
    expense_category_summary = df.groupby('Expense Category')['Amount'].sum().reset_index()
    print(f"\n💰 Total by Expense Category:")
    print(expense_category_summary.sort_values(by='Amount', ascending=False).to_string())

    # Group by Merchant Category
    merchant_category_summary = df.groupby('Merchant Category')['Amount'].sum().reset_index()
    merchant_category_filtered = merchant_category_summary[merchant_category_summary['Amount'] > 100].sort_values(
        by='Amount', ascending=False)
    print(f"\n🏪 Total by Merchant Category (> $100):")
    print(merchant_category_filtered.to_string())

    # Top 5 transactions per Expense Category
    print(f"\n📋 Top 5 Transactions per Expense Category:")
    for category in df['Expense Category'].unique():
        print(f"\n--- {category} ---")
        top_5_transactions = df[df['Expense Category'] == category].sort_values(
            by='Amount', ascending=False).head(5)
        if not top_5_transactions.empty:
            print(top_5_transactions[['Posting Date', 'Description', 'Amount']].to_string())

    # Dining & Entertainment Analysis
    dining_entertainment_expenses = df[df['Merchant Category'].str.contains(
        r'EATING|DINING|BARS|DRINKING', case=False, na=False)]
    dining_entertainment_total = dining_entertainment_expenses['Amount'].sum()
    print(f"\n🍽️ Total Dining & Entertainment: ${dining_entertainment_total:.2f}")

    # Insurance Analysis
    insurance_expenses = df[df['Merchant Category'] == 'INSURANCE-SALES & UNDERWRITING']
    insurance_total = insurance_expenses['Amount'].sum()
    print(f"🛡️ Total Insurance: ${insurance_total:.2f}")

    # Travel Expenses Analysis
    travel_expenses = df[df['Merchant Category'].str.contains(
        r'FUEL|PARKING|TAXI|TRANSPORT|TRAVEL|AIR|CAR|BUS|RENTAL|AUTOMOBILE', case=False, na=False)]
    travel_total = travel_expenses['Amount'].sum()
    print(f"✈️ Total Travel Expenses: ${travel_total:.2f}")
    
    return merchant_category_filtered


def create_checking_account_summary(df):
    """
    Create a summary DataFrame for checking account expenses
    
    Args:
        df: Checking account DataFrame with Description and Amount columns
    
    Returns:
        DataFrame with expense categories and totals
    """
    # Define expense patterns and their categories
    expense_patterns = {
        'Bank Service Charges': r'Monthly Fee|Service Charge|ATM Fee',
        'Payroll Expenses': r'PAYCHEX.*INVOICE',
        'Accounting Fees': r'MATHEWSCPA',
        'Automobile Expense': r'LINCOLN',
        'Utilities': r'PG&E|COMCAST|AT&T|VERIZON|PACIFIC GAS',
        'Insurance Expense': r'INSURANCE|GEICO|STATE FARM',
        'Office Supplies': r'STAPLES|OFFICE DEPOT|AMAZON',
        'Software': r'MICROSOFT|ADOBE|GOOGLE|SOFTWARE',
        'Telephone Expense': r'PHONE|WIRELESS|MOBILE',
    }
    
    # Create a list to store categorized expenses
    categorized_expenses = []
    
    for category, pattern in expense_patterns.items():
        matching_transactions = df[df['Description'].str.contains(pattern, case=False, na=False)]
        if not matching_transactions.empty:
            total_amount = matching_transactions['Amount'].sum()
            categorized_expenses.append({
                'Category': category,
                'Amount': abs(total_amount)  # Use absolute value for consistency
            })
    
    # Create DataFrame from categorized expenses
    summary_df = pd.DataFrame(categorized_expenses)
    
    # Filter out categories with zero or very small amounts
    summary_df = summary_df[summary_df['Amount'] > 0.01]
    
    # Sort by amount descending
    summary_df = summary_df.sort_values(by='Amount', ascending=False).reset_index(drop=True)
    
    return summary_df


def create_checking_account_summary_with_ids(df):
    """
    Create a summary DataFrame for checking account expenses WITH transaction ID tracking
    
    Args:
        df: Checking account DataFrame with Description and Amount columns
    
    Returns:
        Tuple of (df_with_ids, summary_df, transaction_id_map)
    """
    # Add Transaction IDs
    df = df.copy()
    df['Transaction_ID'] = range(1, len(df) + 1)
    
    # Define expense patterns and their categories
    expense_patterns = {
        'Bank Service Charges': r'Monthly Fee|Service Charge|ATM Fee',
        'Payroll Expenses': r'PAYCHEX.*INVOICE',
        'Accounting Fees': r'MATHEWSCPA',
        'Automobile Expense': r'LINCOLN',
        'Utilities': r'PG&E|COMCAST|AT&T|VERIZON|PACIFIC GAS',
        'Insurance Expense': r'INSURANCE|GEICO|STATE FARM',
        'Office Supplies': r'STAPLES|OFFICE DEPOT|AMAZON',
        'Software': r'MICROSOFT|ADOBE|GOOGLE|SOFTWARE',
        'Telephone Expense': r'PHONE|WIRELESS|MOBILE',
    }
    
    # Create a list to store categorized expenses
    categorized_expenses = []
    transaction_id_map = {}  # Map category name to list of transaction IDs
    
    for category, pattern in expense_patterns.items():
        matching_transactions = df[df['Description'].str.contains(pattern, case=False, na=False)]
        if not matching_transactions.empty:
            total_amount = matching_transactions['Amount'].sum()
            categorized_expenses.append({
                'Category': category,
                'Amount': abs(total_amount)  # Use absolute value for consistency
            })
            # Store transaction IDs for this category
            transaction_id_map[category] = matching_transactions['Transaction_ID'].tolist()
    
    # Create DataFrame from categorized expenses
    summary_df = pd.DataFrame(categorized_expenses)
    
    # Filter out categories with zero or very small amounts
    summary_df = summary_df[summary_df['Amount'] > 0.01]
    
    # Sort by amount descending
    summary_df = summary_df.sort_values(by='Amount', ascending=False).reset_index(drop=True)
    
    return df, summary_df, transaction_id_map


def map_checking_openai_to_transactions(df_with_ids, openai_results, transaction_id_map):
    """
    Map OpenAI results back to original checking account transactions
    
    Args:
        df_with_ids: DataFrame with Transaction_ID column
        openai_results: OpenAI categorization results
        transaction_id_map: Dict mapping category -> list of transaction IDs
    
    Returns:
        DataFrame with detailed transaction mapping
    """
    result_rows = []
    
    for ref_category, items in openai_results.items():
        for item in items:
            original_category = item['category']
            
            if original_category in transaction_id_map:
                transaction_ids = transaction_id_map[original_category]
                
                # Get original transactions
                original_txns = df_with_ids[df_with_ids['Transaction_ID'].isin(transaction_ids)]
                
                for _, txn in original_txns.iterrows():
                    result_rows.append({
                        'Transaction_ID': txn['Transaction_ID'],
                        'Date': txn['Date'],
                        'Description': txn['Description'],
                        'Amount': txn['Amount'],
                        'Original_Category': original_category,
                        'OpenAI_Reference_Category': ref_category
                    })
    
    result_df = pd.DataFrame(result_rows)
    if not result_df.empty:
        result_df = result_df.sort_values(['Date', 'Transaction_ID'])
    
    return result_df


def prepare_buz_with_ids(df):
    """
    Prepare buz credit card data with transaction IDs and create summary with ID tracking
    
    Args:
        df: buz credit card DataFrame
    
    Returns:
        Tuple of (df_with_ids, summary_df, transaction_id_map)
    """
    # Add Transaction IDs
    df = df.copy()
    df['Transaction_ID'] = range(1, len(df) + 1)
    
    # Group by Merchant Category and track IDs
    grouped = df.groupby('Merchant Category').agg({
        'Amount': 'sum',
        'Transaction_ID': lambda x: list(x)  # Keep list of transaction IDs
    }).reset_index()
    
    # NO FILTER - Include all merchant categories
    grouped = grouped.sort_values(by='Amount', ascending=False)
    
    # Create transaction_id_map: Merchant Category -> list of transaction IDs
    transaction_id_map = dict(zip(grouped['Merchant Category'], grouped['Transaction_ID']))
    
    # Create summary (just Merchant Category + Amount for OpenAI)
    summary_df = grouped[['Merchant Category', 'Amount']].copy()
    summary_df = summary_df.reset_index(drop=True)
    
    return df, summary_df, transaction_id_map


def map_buz_openai_to_transactions(df_with_ids, openai_results, transaction_id_map):
    """
    Map OpenAI results back to original buz credit card transactions
    
    Args:
        df_with_ids: DataFrame with Transaction_ID column
        openai_results: OpenAI categorization results
        transaction_id_map: Dict mapping Merchant Category -> list of transaction IDs
    
    Returns:
        DataFrame with detailed transaction mapping
    """
    result_rows = []
    
    for ref_category, items in openai_results.items():
        for item in items:
            original_category = item['category']
            
            if original_category in transaction_id_map:
                transaction_ids = transaction_id_map[original_category]
                
                # Get original transactions
                original_txns = df_with_ids[df_with_ids['Transaction_ID'].isin(transaction_ids)]
                
                for _, txn in original_txns.iterrows():
                    result_rows.append({
                        'Transaction_ID': txn['Transaction_ID'],
                        'Date': txn['Posting Date'],
                        'Description': txn['Description'],
                        'Amount': txn['Amount'],
                        'Merchant_Category': txn['Merchant Category'],
                        'Original_Category': original_category,
                        'OpenAI_Reference_Category': ref_category
                    })
    
    result_df = pd.DataFrame(result_rows)
    if not result_df.empty:
        result_df = result_df.sort_values(['Date', 'Transaction_ID'])
    
    return result_df


def prepare_personal_with_ids(df):
    """
    Prepare Personal credit card data with transaction IDs and create summary with ID tracking
    
    Args:
        df: DataFrame with Personal credit card transactions
        
    Returns:
        tuple: (df_with_ids, summary_df, transaction_id_map)
            - df_with_ids: Original DataFrame with Transaction_ID column added
            - summary_df: Summary grouped by Description (merchant)
            - transaction_id_map: Dict mapping Description -> list of transaction IDs
    """
    # Create a copy to avoid modifying original
    df_with_ids = df.copy()
    
    # Add Transaction_ID (sequential numbering)
    df_with_ids['Transaction_ID'] = range(1, len(df_with_ids) + 1)
    
    print(f"✓ Added Transaction IDs to {len(df_with_ids)} transactions")
    
    # Group by Description (merchant name) - NO FILTER, include ALL merchants
    merchant_summary = df_with_ids.groupby('Description').agg({
        'Amount': 'sum'
    }).reset_index()
    
    merchant_summary = merchant_summary.sort_values('Amount', ascending=False)
    
    print(f"✓ Tracking {len(merchant_summary)} merchant descriptions")
    
    # Create transaction ID map: Description -> [list of Transaction_IDs]
    transaction_id_map = {}
    for description in merchant_summary['Description']:
        transaction_ids = df_with_ids[df_with_ids['Description'] == description]['Transaction_ID'].tolist()
        transaction_id_map[description] = transaction_ids
    
    return df_with_ids, merchant_summary, transaction_id_map


def map_personal_openai_to_transactions(df_with_ids, openai_results, transaction_id_map):
    """
    Map OpenAI categorization results back to individual Personal transactions
    
    Args:
        df_with_ids: DataFrame with Transaction_ID column
        openai_results: Dict from OpenAI categorization (reference_category -> list of items)
        transaction_id_map: Dict mapping Description -> list of Transaction_IDs
        
    Returns:
        DataFrame with columns: Transaction_ID, Date, Description, Amount, 
                                Original_Category, OpenAI_Reference_Category
    """
    result_rows = []
    
    # Iterate through OpenAI results
    for ref_category, items in openai_results.items():
        for item in items:
            original_category = item['category']
            
            # Find transaction IDs for this merchant description
            if original_category in transaction_id_map:
                txn_ids = transaction_id_map[original_category]
                
                # Get all transactions with these IDs
                for txn_id in txn_ids:
                    txn = df_with_ids[df_with_ids['Transaction_ID'] == txn_id].iloc[0]
                    result_rows.append({
                        'Transaction_ID': txn['Transaction_ID'],
                        'Date': txn['Posting Date'],
                        'Description': txn['Description'],
                        'Amount': txn['Amount'],
                        'Original_Category': original_category,
                        'OpenAI_Reference_Category': ref_category
                    })
    
    result_df = pd.DataFrame(result_rows)
    if not result_df.empty:
        result_df = result_df.sort_values(['Date', 'Transaction_ID'])
    
    return result_df


def prepare_amex_with_ids(df):
    """
    Prepare Amex credit card data with transaction IDs and create summary with ID tracking
    
    Args:
        df: DataFrame with Amex credit card transactions
        
    Returns:
        tuple: (df_with_ids, summary_df, transaction_id_map)
            - df_with_ids: Original DataFrame with Transaction_ID column added
            - summary_df: Summary grouped by Category
            - transaction_id_map: Dict mapping Category -> list of transaction IDs
    """
    # Create a copy to avoid modifying original
    df_with_ids = df.copy()
    
    # Add Transaction_ID (sequential numbering)
    df_with_ids['Transaction_ID'] = range(1, len(df_with_ids) + 1)
    
    print(f"✓ Added Transaction IDs to {len(df_with_ids)} transactions")
    
    # Group by Category - NO FILTER, include ALL categories
    category_summary = df_with_ids.groupby('Category').agg({
        'Amount': 'sum'
    }).reset_index()
    
    category_summary = category_summary.sort_values('Amount', ascending=False)
    
    print(f"✓ Tracking {len(category_summary)} Amex categories")
    
    # Create transaction ID map: Category -> [list of Transaction_IDs]
    transaction_id_map = {}
    for category in category_summary['Category']:
        transaction_ids = df_with_ids[df_with_ids['Category'] == category]['Transaction_ID'].tolist()
        transaction_id_map[category] = transaction_ids
    
    return df_with_ids, category_summary, transaction_id_map


def map_amex_openai_to_transactions(df_with_ids, openai_results, transaction_id_map):
    """
    Map OpenAI categorization results back to individual Amex transactions
    
    Args:
        df_with_ids: DataFrame with Transaction_ID column
        openai_results: Dict from OpenAI categorization (reference_category -> list of items)
        transaction_id_map: Dict mapping Category -> list of Transaction_IDs
        
    Returns:
        DataFrame with columns: Transaction_ID, Date, Description, Amount, 
                                Original_Category, OpenAI_Reference_Category
    """
    result_rows = []
    
    # Iterate through OpenAI results
    for ref_category, items in openai_results.items():
        for item in items:
            original_category = item['category']
            
            # Find transaction IDs for this Amex category
            if original_category in transaction_id_map:
                txn_ids = transaction_id_map[original_category]
                
                # Get all transactions with these IDs
                for txn_id in txn_ids:
                    txn = df_with_ids[df_with_ids['Transaction_ID'] == txn_id].iloc[0]
                    result_rows.append({
                        'Transaction_ID': txn['Transaction_ID'],
                        'Date': txn['Date'],
                        'Description': txn['Description'],
                        'Amount': txn['Amount'],
                        'Original_Category': original_category,
                        'OpenAI_Reference_Category': ref_category
                    })
    
    result_df = pd.DataFrame(result_rows)
    if not result_df.empty:
        result_df = result_df.sort_values(['Date', 'Transaction_ID'])
    
    return result_df


# ============================================================================
# �️  CLEANUP OLD FILES
# ============================================================================

print("\n" + "="*70)
print("CLEANING UP OLD OUTPUT FILES")
print("="*70)

# List of all output files that might exist from previous runs
output_files_to_delete = [
    # Summary files
    'checking_account_category_summary.csv',
    'buz_merchant_category_summary.csv',
    'personal_merchant_category_summary.csv',
    'amex_category_summary.csv',
    
    # Consolidated summaries
    'consolidated_expense_summary.xlsx',
    'consolidated_expense_summary.csv',
    
    # Detailed categorization files (OLD FORMAT - NO LONGER NEEDED)
    'checking-account_detailed_categorization.csv',
    'buz-creditcard_detailed_categorization.csv',
    'personal-creditcard_detailed_categorization.csv',
    'amex-creditcard_detailed_categorization.csv',
    
    # New detailed transaction mapping files
    'checking_account_detailed_transaction_mapping.csv',
    'buz_creditcard_detailed_transaction_mapping.csv',
    'personal_creditcard_detailed_transaction_mapping.csv',
    'amex_creditcard_detailed_transaction_mapping.csv',
    
    # OpenAI log files (from previous runs)
    'openai_log_checking_account.txt',
    'openai_log_buz_creditcard.txt',
    'openai_log_personal_creditcard.txt',
    'openai_log_amex_creditcard.txt',
    
    # Unmapped transaction files (if they exist from previous runs)
    'unmapped_transactions_checking_account.csv',
    'unmapped_transactions_buz_creditcard.csv',
    'unmapped_transactions_personal_creditcard.csv',
    'unmapped_transactions_amex_creditcard.csv',
    'unmapped_openai_items_checking_account.csv',
    'unmapped_openai_items_buz_creditcard.csv',
    'unmapped_openai_items_personal_creditcard.csv',
    'unmapped_openai_items_amex_creditcard.csv',
]

deleted_count = 0
for file in output_files_to_delete:
    if os.path.exists(file):
        os.remove(file)
        deleted_count += 1

if deleted_count > 0:
    print(f"🗑️  Deleted {deleted_count} old output file(s)")
else:
    print("✓ No old files to delete")

print("="*70)

exit()

# ============================================================================
# �💳 CHECKING ACCOUNT ANALYSIS
# ============================================================================

print("\n" + "="*70)
print("CHECKING ACCOUNT ANALYSIS")
print("="*70)

# Read the file line by line to find the header
with open(CHECKING_STATEMENT_FILE, 'r', encoding=CSV_ENCODING) as f:
    lines = f.readlines()

header_row_index = -1
for i, line in enumerate(lines):
    if line.startswith('Date'):
        header_row_index = i
        break

if header_row_index == -1:
    raise ValueError("Header starting with 'Date' not found in the CSV file.")

# Read checking account data
df_checking_account = pd.read_csv(CHECKING_STATEMENT_FILE, encoding=CSV_ENCODING, 
                                   skiprows=header_row_index, parse_dates=['Date'])

# Remove unnamed columns
df_checking_clean = df_checking_account.loc[:, ~df_checking_account.columns.str.startswith('Unnamed')]

# Convert Amount to numeric
df_checking_clean['Amount'] = pd.to_numeric(df_checking_clean['Amount'], errors='coerce')

# Create checking account summary WITH transaction IDs
df_checking_with_ids, checking_account_summary, checking_id_map = create_checking_account_summary_with_ids(df_checking_clean)

print(f"✓ Added Transaction IDs to {len(df_checking_with_ids)} transactions")
print(f"✓ Tracking {len(checking_id_map)} expense categories")

# Monthly Fees Analysis
monthly_fees = df_checking_with_ids.loc[df_checking_with_ids['Description'].str.startswith('Monthly Fee')]
monthly_fee_total = monthly_fees['Amount'].sum()

print("\n📊 Monthly Fees:")
print(monthly_fees.to_string())
print(f"\nTotal BOA Monthly Fees: ${monthly_fee_total:.2f}")

# Paychex Invoice Analysis
paychex_invoice_mask = df_checking_with_ids['Description'].str.contains('PAYCHEX.*INVOICE', case=False, na=False)
paychex_invoice_total = df_checking_with_ids.loc[paychex_invoice_mask, 'Amount'].sum()
print(f"\nTotal PAYCHEX (containing PAYCHEX%INVOICE): ${paychex_invoice_total:.2f}")

# Mathews CPA Fees
mathews_cpa_fees = df_checking_with_ids[df_checking_with_ids['Description'].str.contains(
    r'MATHEWSCPA*', case=False, na=False)]
mathews_cpa_total = mathews_cpa_fees['Amount'].sum()
print(f"Total MATHEWSCPA: ${mathews_cpa_total:.2f}")

# Lincoln Car Fees
lincoln_car_fees = df_checking_with_ids[df_checking_with_ids['Description'].str.contains(
    r'LINCOLN*', case=False, na=False)]
lincoln_car_total = lincoln_car_fees['Amount'].sum()
print(f"Total Lincoln Car Fee: ${lincoln_car_total:.2f}")

print(f"\n📊 Checking Account Summary by Category:")
print(checking_account_summary.to_string())

# Save checking account summary
checking_account_summary.to_csv(CHECKING_ACCOUNT_SUMMARY_FILE, index=False)
if IN_COLAB:
    files.download(CHECKING_ACCOUNT_SUMMARY_FILE)

# ============================================================================
# 💳 CREDIT CARD #1 - buz (SINGLE FILE - KEPT SEPARATE)
# ============================================================================

print("\n" + "="*70)
print("CREDIT CARD #1 - buz")
print("="*70)

df_credit_buz = parse_credit_card_statement(buz_CREDIT_CARD_FILE)

# Clean and process buz credit card data
df_credit_buz = df_credit_buz[df_credit_buz['Transaction Type'] != 'C']
df_credit_buz['Amount'] = pd.to_numeric(df_credit_buz['Amount'], errors='coerce')

# Prepare with transaction IDs and create summary
df_buz_with_ids, buz_merchant_summary, buz_id_map = prepare_buz_with_ids(df_credit_buz)

buz_grand_total = df_buz_with_ids['Amount'].sum()
print(f"\n💰 buz Credit Card Grand Total: ${buz_grand_total:.2f}")
print(f"📝 Total Transactions: {len(df_buz_with_ids)}")
print(f"✓ Added Transaction IDs to {len(df_buz_with_ids)} transactions")
print(f"✓ Tracking {len(buz_id_map)} merchant categories")

# Show detailed analysis
print("\n📊 buz - Expense Analysis")
print("="*70)

# Group by Expense Category
expense_category_summary = df_buz_with_ids.groupby('Expense Category')['Amount'].sum().reset_index()
print(f"\n💰 Total by Expense Category:")
print(expense_category_summary.sort_values(by='Amount', ascending=False).to_string())

print(f"\n🏪 Total by Merchant Category (ALL merchants - no filter):")
print(buz_merchant_summary.to_string())

# Save buz merchant summary
buz_merchant_summary.to_csv(buz_MERCHANT_SUMMARY_FILE, index=False)
if IN_COLAB:
    files.download(buz_MERCHANT_SUMMARY_FILE)

# ============================================================================
# 💳 CREDIT CARD #2 - Personal (MULTIPLE FILES - KEPT SEPARATE)
# ============================================================================

print("\n" + "="*70)
print("CREDIT CARD #2 - Personal")
print("="*70)

df_credit_personal = load_multiple_credit_card_files(personal_CREDIT_CARD_FOLDER, file_type='simple')

# Clean and process Personal credit card data
# No need to filter Transaction Type since we already filtered in load function
df_credit_personal['Amount'] = pd.to_numeric(df_credit_personal['Amount'], errors='coerce')

# Prepare with transaction IDs and create summary
df_personal_with_ids, personal_merchant_summary, personal_id_map = prepare_personal_with_ids(df_credit_personal)

personal_grand_total = df_personal_with_ids['Amount'].sum()
print(f"\n💰 Personal Credit Card Grand Total: ${personal_grand_total:.2f}")
print(f"📝 Total Transactions: {len(df_personal_with_ids)}")

print(f"\n🏪 Total by Merchant (ALL merchants - no filter):")
print(personal_merchant_summary.to_string())

# Save Personal merchant summary
personal_merchant_summary.to_csv(personal_MERCHANT_SUMMARY_FILE, index=False)
if IN_COLAB:
    files.download(personal_MERCHANT_SUMMARY_FILE)

# ============================================================================
# 💳 AMEX CARD ANALYSIS (KEPT SEPARATE)
# ============================================================================

print("\n" + "="*70)
print("AMEX CARD ANALYSIS")
print("="*70)

# Read Amex file
with open(AMEX_STATEMENT_FILE, 'r', encoding=CSV_ENCODING) as f:
    lines = f.readlines()

header_row_index = -1
for i, line in enumerate(lines):
    if line.startswith('Date'):
        header_row_index = i
        break

if header_row_index == -1:
    raise ValueError("Header starting with 'Date' not found in Amex CSV file.")

df_amex = pd.read_csv(AMEX_STATEMENT_FILE, encoding=CSV_ENCODING, 
                      skiprows=header_row_index, parse_dates=['Date'])

# Filter positive amounts only
df_amex['Amount'] = pd.to_numeric(df_amex['Amount'], errors='coerce')
df_amex_positive = df_amex[df_amex['Amount'] > 0].copy()

# Prepare with transaction IDs and create summary
df_amex_with_ids, amex_category_summary, amex_id_map = prepare_amex_with_ids(df_amex_positive)

print("\n📊 Amex - Total by Category (positive amounts only):")
print(amex_category_summary.sort_values(by='Amount', ascending=False).to_string())

# Save Amex summary
amex_category_summary.sort_values(by='Amount', ascending=False).to_csv(AMEX_CATEGORY_SUMMARY_FILE, index=False)
if IN_COLAB:
    files.download(AMEX_CATEGORY_SUMMARY_FILE)

# Top 5 transactions per Category
print("\n📋 Amex - Top 5 Transactions per Category:")
sorted_amex_categories = amex_category_summary.sort_values(by='Amount', ascending=False)['Category'].tolist()

for category in sorted_amex_categories:
    print(f"\n--- {category} ---")
    top_5_amex = df_amex_with_ids[df_amex_with_ids['Category'] == category].sort_values(
        by='Amount', ascending=False).head(5)
    if not top_5_amex.empty:
        print(top_5_amex[['Date', 'Description', 'Amount']].to_string())

# ============================================================================
# 🤖 OPENAI CATEGORIZATION (ALL CARDS KEPT SEPARATE)
# ============================================================================

print("\n" + "="*70)
print("OPENAI EXPENSE CATEGORIZATION")
print("="*70)

# Prepare DataFrames for categorization - EACH ACCOUNT SEPARATE
dataframes_for_categorization = {
    'Checking-Account': checking_account_summary,
    'buz-CreditCard': buz_merchant_summary,
    'personal-CreditCard': personal_merchant_summary,
    'Amex-CreditCard': amex_category_summary,
}

print("✓ Setup complete! Ready to categorize expenses.")
print(f"📊 Processing {len(dataframes_for_categorization)} separate accounts (1 checking + 3 credit cards)")

# Categorize all DataFrames
all_categorized_results = categorize_multiple_dataframes(dataframes_for_categorization, REFERENCE_CATEGORIES)

# Create consolidated summary
print("\n" + "="*70)
print("CREATING CONSOLIDATED SUMMARY (SEPARATE ACCOUNT TOTALS)")
print("="*70)
consolidated_expense_summary = create_consolidated_summary(all_categorized_results, REFERENCE_CATEGORIES)

print("\n📈 CONSOLIDATED SUMMARY BY REFERENCE CATEGORY:")
print("="*70)
print(consolidated_expense_summary.to_string(index=False))
print("="*70)

# Export consolidated summary
consolidated_expense_summary.to_excel(CONSOLIDATED_SUMMARY_EXCEL_FILE, index=False, engine='openpyxl')
consolidated_expense_summary.to_csv(CONSOLIDATED_SUMMARY_CSV_FILE, index=False)

print(f"\n✅ Consolidated summary exported to: {CONSOLIDATED_SUMMARY_EXCEL_FILE}")
print(f"✅ CSV backup exported to: {CONSOLIDATED_SUMMARY_CSV_FILE}")

if IN_COLAB:
    print("\n📥 Downloading files...")
    files.download(CONSOLIDATED_SUMMARY_EXCEL_FILE)
    files.download(CONSOLIDATED_SUMMARY_CSV_FILE)
    print("✅ Files downloaded!")
else:
    print(f"\n📁 Files saved to current directory")

# ============================================================================
# 🔄 MAP CHECKING ACCOUNT TRANSACTIONS TO OPENAI CATEGORIZATION
# ============================================================================

print("\n" + "="*70)
print("MAPPING CHECKING ACCOUNT TRANSACTIONS")
print("="*70)

# Map OpenAI results back to individual transactions
checking_detailed_file = 'checking_account_detailed_transaction_mapping.csv'
checking_detailed_mapping = map_checking_openai_to_transactions(
    df_checking_with_ids,
    all_categorized_results['Checking-Account'],
    checking_id_map
)

# Save detailed mapping
checking_detailed_mapping.to_csv(checking_detailed_file, index=False)

# Show statistics
if not checking_detailed_mapping.empty:
    total_amount = checking_detailed_mapping['Amount'].sum()
    num_transactions = len(checking_detailed_mapping)
    num_categories = checking_detailed_mapping['OpenAI_Reference_Category'].nunique()
    
    print(f"✅ Checking Account Transaction Mapping:")
    print(f"   📄 File: {checking_detailed_file}")
    print(f"   📊 Transactions mapped: {num_transactions}")
    print(f"   💰 Total Amount: ${abs(total_amount):,.2f}")
    print(f"   🏷️  Categories: {num_categories}")
    
    # Validation
    summary_total = checking_account_summary['Amount'].sum()
    difference = abs(abs(total_amount) - summary_total)
    
    if difference < 0.01:
        print(f"   ✅ Totals match! (Difference: ${difference:.2f})")
    else:
        print(f"   ⚠️  Totals don't match! Summary: ${summary_total:.2f}, Detailed: ${abs(total_amount):.2f}, Diff: ${difference:.2f}")
else:
    print(f"❌ No transactions were mapped!")

if IN_COLAB:
    files.download(checking_detailed_file)

# ============================================================================
# 🔄 MAP buz CREDIT CARD TRANSACTIONS TO OPENAI CATEGORIZATION
# ============================================================================

print("\n" + "="*70)
print("MAPPING buz CREDIT CARD TRANSACTIONS")
print("="*70)

# Map OpenAI results back to individual transactions
buz_detailed_file = 'buz_creditcard_detailed_transaction_mapping.csv'
buz_detailed_mapping = map_buz_openai_to_transactions(
    df_buz_with_ids,
    all_categorized_results['buz-CreditCard'],
    buz_id_map
)

# Save detailed mapping
buz_detailed_mapping.to_csv(buz_detailed_file, index=False)

# Show statistics
if not buz_detailed_mapping.empty:
    total_amount = buz_detailed_mapping['Amount'].sum()
    num_transactions = len(buz_detailed_mapping)
    num_categories = buz_detailed_mapping['OpenAI_Reference_Category'].nunique()
    
    print(f"✅ buz Credit Card Transaction Mapping:")
    print(f"   📄 File: {buz_detailed_file}")
    print(f"   📊 Transactions mapped: {num_transactions}")
    print(f"   💰 Total Amount: ${total_amount:,.2f}")
    print(f"   🏷️  Categories: {num_categories}")
    
    # Validation
    summary_total = buz_merchant_summary['Amount'].sum()
    difference = abs(total_amount - summary_total)
    
    if difference < 0.01:
        print(f"   ✅ Totals match! (Difference: ${difference:.2f})")
    else:
        print(f"   ⚠️  Totals don't match! Summary: ${summary_total:.2f}, Detailed: ${total_amount:.2f}, Diff: ${difference:.2f}")
else:
    print(f"❌ No transactions were mapped!")

if IN_COLAB:
    files.download(buz_detailed_file)

# ============================================================================
# 🔄 MAP Personal CREDIT CARD TRANSACTIONS TO OPENAI CATEGORIZATION
# ============================================================================

print("\n" + "="*70)
print("MAPPING Personal CREDIT CARD TRANSACTIONS")
print("="*70)

# Map OpenAI results back to individual transactions
personal_detailed_file = 'personal_creditcard_detailed_transaction_mapping.csv'
personal_detailed_mapping = map_personal_openai_to_transactions(
    df_personal_with_ids,
    all_categorized_results['personal-CreditCard'],
    personal_id_map
)

# Save detailed mapping
personal_detailed_mapping.to_csv(personal_detailed_file, index=False)

# Show statistics
if not personal_detailed_mapping.empty:
    total_amount = personal_detailed_mapping['Amount'].sum()
    num_transactions = len(personal_detailed_mapping)
    num_categories = personal_detailed_mapping['OpenAI_Reference_Category'].nunique()
    
    print(f"✅ Personal Credit Card Transaction Mapping:")
    print(f"   📄 File: {personal_detailed_file}")
    print(f"   📊 Transactions mapped: {num_transactions}")
    print(f"   💰 Total Amount: ${total_amount:,.2f}")
    print(f"   🏷️  Categories: {num_categories}")
    
    # Validation
    summary_total = personal_merchant_summary['Amount'].sum()
    difference = abs(total_amount - summary_total)
    
    if difference < 0.01:
        print(f"   ✅ Totals match! (Difference: ${difference:.2f})")
    else:
        print(f"   ⚠️  Totals don't match! Summary: ${summary_total:.2f}, Detailed: ${total_amount:.2f}, Diff: ${difference:.2f}")
else:
    print(f"❌ No transactions were mapped!")

if IN_COLAB:
    files.download(personal_detailed_file)

# ============================================================================
# 🔄 MAP AMEX CREDIT CARD TRANSACTIONS TO OPENAI CATEGORIZATION
# ============================================================================

print("\n" + "="*70)
print("MAPPING AMEX CREDIT CARD TRANSACTIONS")
print("="*70)

# Map OpenAI results back to individual transactions
amex_detailed_file = 'amex_creditcard_detailed_transaction_mapping.csv'
amex_detailed_mapping = map_amex_openai_to_transactions(
    df_amex_with_ids,
    all_categorized_results['Amex-CreditCard'],
    amex_id_map
)

# Save detailed mapping
amex_detailed_mapping.to_csv(amex_detailed_file, index=False)

# Show statistics
if not amex_detailed_mapping.empty:
    total_amount = amex_detailed_mapping['Amount'].sum()
    num_transactions = len(amex_detailed_mapping)
    num_categories = amex_detailed_mapping['OpenAI_Reference_Category'].nunique()
    
    print(f"✅ Amex Credit Card Transaction Mapping:")
    print(f"   📄 File: {amex_detailed_file}")
    print(f"   📊 Transactions mapped: {num_transactions}")
    print(f"   💰 Total Amount: ${total_amount:,.2f}")
    print(f"   🏷️  Categories: {num_categories}")
    
    # Validation
    summary_total = amex_category_summary['Amount'].sum()
    difference = abs(total_amount - summary_total)
    
    if difference < 0.01:
        print(f"   ✅ Totals match! (Difference: ${difference:.2f})")
    else:
        print(f"   ⚠️  Totals don't match! Summary: ${summary_total:.2f}, Detailed: ${total_amount:.2f}, Diff: ${difference:.2f}")
else:
    print(f"❌ No transactions were mapped!")

if IN_COLAB:
    files.download(amex_detailed_file)

# Detailed breakdown for each DataFrame
print("\n" + "="*70)
print("DETAILED BREAKDOWN BY ACCOUNT (KEPT SEPARATE)")
print("="*70)

for df_name, categorized_data in all_categorized_results.items():
    print(f"\n{'='*70}")
    print(f"📋 {df_name.upper()} - DETAILED BREAKDOWN")
    print(f"{'='*70}")

    formatted_output = format_categorized_output(categorized_data)
    print(formatted_output)

    # Calculate grand total
    grand_total = sum(item['amount'] for items in categorized_data.values() for item in items)
    print(f"\n{'='*70}")
    print(f"💰 {df_name} GRAND TOTAL: ${grand_total:,.2f}")
    print(f"{'='*70}\n")

print("\n✅ All processing complete!")
print("\n📋 SUMMARY:")
print(f"   • Checking Account: ${checking_account_summary['Amount'].sum():.2f}")
print(f"   • buz Credit Card: ${buz_grand_total:.2f}")
print(f"   • Personal Credit Card: ${personal_grand_total:.2f}")
print(f"   • Amex Card: ${df_amex_positive['Amount'].sum():.2f}")
print(f"   • Total across all accounts: ${checking_account_summary['Amount'].sum() + buz_grand_total + personal_grand_total + df_amex_positive['Amount'].sum():.2f}")