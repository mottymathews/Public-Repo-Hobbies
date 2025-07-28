
# 🧬 Family Tree Excel to GEDCOM Converter

This project provides a simple Python script to convert family tree data stored in an Excel spreadsheet into a [GEDCOM](https://en.wikipedia.org/wiki/GEDCOM) file — a standard format for genealogy data exchange.

## 📁 Project Structure

- `familyTree_excel_to_gedcom_final.py` — The main Python script that performs the conversion.
- `family_tree_sample.xlsx` — A sample Excel file with family tree data.
- `family_tree_sample.ged` — The generated GEDCOM file from the sample Excel.

## 📥 Input Format
> **Note:** The Excel file should contain a sheet named **`RealWorkingSheet`**.


The script expects an Excel file with the following headers:

| Full Name | Gender | Dead/Alive | Date of Birth (mm/dd/yyyy) | Date of Death (mm/dd/yyyy) | Father Full Name | Mother Full Name | Spouse Full Name | Children |
|-----------|--------|------------|-----------------------------|-----------------------------|------------------|------------------|------------------|----------|

Each row represents one individual.

### Sample Row:

```
John Mathews | Male | Alive | 01/15/1960 |  | Isaac Mathews | Anna Mathews | Mary Mathews | David Mathews
```

## ⚙️ How It Works

The script performs the following steps:
1. Reads the Excel file into a DataFrame.
2. Maps relationships between individuals (parents, spouses, children).
3. Generates GEDCOM records with unique identifiers.
4. Outputs a `.ged` file compatible with genealogy software (e.g., Gramps, Ancestry, etc.).

## 🚀 Usage

### Requirements
- Python 3.x
- pandas (install via `pip install pandas`)

### Run the script

```bash
python familyTree_excel_to_gedcom_final.py
```

By default, it reads `family_tree_sample.xlsx` and generates `family_tree_sample.ged`.

## 🧪 Sample Output

The output GEDCOM file (`.ged`) can be imported into:
- [Gramps](https://gramps-project.org/)
- [MyHeritage](https://www.myheritage.com/)
- [Family Tree Builder](https://www.familytreebuilder.com/)

## 📄 License

MIT License

---


