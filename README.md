# WooCommerce to Shopify Product Converter (Matrixify-ready)

A Python/pandas script that converts a WooCommerce product CSV export into an Excel file
formatted for [Matrixify](https://matrixify.app) import into Shopify. It removes the manual
cleanup of variable products, prices, categories and images.

## What it does
- Builds URL-safe Shopify handles from product names
- Flattens variable products: each variation inherits its parent's handle, title,
  description, categories and weight; the parent row itself is removed
- Maps sale/regular price to `Variant Price` / `Variant Compare At Price`
- Enables inventory tracking only on rows that have a stock value
- Reduces category breadcrumbs (`Clothing > Hoodies`) to the leaf (`Hoodies`)
- Puts extra product images on additional rows, as Shopify/Matrixify expect
- Marks downloadable/virtual products as not requiring shipping
- Prints warnings for anything it drops or cannot resolve

## Usage
```bash
pip install -r requirements.txt
python cleaner.py --input sample_products.csv --output matrixify_ready_products.xlsx
```
`sample_products.csv` is WooCommerce's public demo catalog; `matrixify_ready_products.xlsx`
is the result.

## Input requirements
A standard WooCommerce product export containing at least: `Type`, `SKU`, `Name`, `Parent`,
`Description`, `Categories`, `Regular price`, `Sale price`, `Stock`, `Images`,
`Weight (lbs)`, `Attribute 1/2 name`, `Attribute 1/2 value(s)`.

## Known limitations
- Variations must reference their parent by **SKU** in the `Parent` column
  (not `id:123`). Unmatched variations are reported and import as separate products.
- `grouped` and `external` WooCommerce products are dropped (no Shopify equivalent).
- Two different products with the same name produce the same handle.
- Supports two product options (Shopify allows three).
- Always run a Matrixify **dry run** and review the result before importing to a live store.

## Stack
Python 3, pandas, numpy, openpyxl