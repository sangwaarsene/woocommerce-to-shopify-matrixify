"""Convert a WooCommerce product CSV export into a Matrixify-ready Excel file for Shopify."""
import argparse
import sys

import numpy as np
import pandas as pd

MATRIXIFY_COLUMNS = [
    "Handle", "Command", "Title", "Body HTML", "Variant SKU", "Variant Price",
    "Variant Compare At Price", "Variant Inventory Tracker", "Variant Inventory Qty",
    "Variant Inventory Policy", "Variant Weight", "Variant Weight Unit",
    "Variant Requires Shipping", "Image Src", "Image Position",
    "Option1 Name", "Option1 Value", "Option2 Name", "Option2 Value",
    "Custom Collections",
]

# WooCommerce types with no sensible Shopify equivalent are dropped (and reported).
DROPPED_TYPES = ["grouped", "external"]


def warn(msg):
    print(f"WARNING: {msg}", file=sys.stderr)


def leaf_categories(value):
    """'Clothing > Hoodies, Sale > Summer' -> 'Hoodies, Summer'."""
    if pd.isna(value):
        return np.nan
    leaves = [part.split(">")[-1].strip() for part in str(value).split(",")]
    return ", ".join(dict.fromkeys(l for l in leaves if l))


def convert(df):
    df = df.copy()

    # 1. URL-friendly handles
    df["Handle"] = (
        df["Name"].astype(str).str.lower()
        .str.replace(r"[^a-z0-9\s-]", "", regex=True)
        .str.replace(r"\s+", "-", regex=True)
    )

    # 2. Parent lookups from 'variable' rows (Parent column must contain the parent SKU)
    parents = df[(df["Type"] == "variable") & df["SKU"].notna()].drop_duplicates("SKU").set_index("SKU")
    is_variant = df["Type"] == "variation"
    parent_key = df.loc[is_variant, "Parent"]

    orphans = parent_key[~parent_key.isin(parents.index)]
    if len(orphans):
        warn(f"{len(orphans)} variation row(s) have a Parent that is not a known parent SKU "
             f"(e.g. {orphans.iloc[0]!r}). They will import as separate products.")

    # 3. Push parent data down to variations
    for col in ("Handle", "Name", "Description", "Categories"):
        if col in df.columns:
            df.loc[is_variant, col] = parent_key.map(parents[col]).fillna(df.loc[is_variant, col])
    if "Weight (lbs)" in df.columns:  # variations often leave weight blank
        df.loc[is_variant, "Weight (lbs)"] = df.loc[is_variant, "Weight (lbs)"].fillna(
            parent_key.map(parents["Weight (lbs)"]))

    # 4. Drop parent rows and types Shopify cannot represent
    dropped = df[df["Type"].isin(["variable"] + DROPPED_TYPES)]
    skipped = dropped[dropped["Type"].isin(DROPPED_TYPES)]
    if len(skipped):
        warn(f"Dropped {len(skipped)} row(s) with unsupported type: "
             + ", ".join(f"{r.Name} ({r.Type})" for r in skipped.itertuples()))
    df = df[~df["Type"].isin(["variable"] + DROPPED_TYPES)].copy()

    # 5. Pricing: sale price wins; regular price becomes Compare At
    df["Sale price"] = pd.to_numeric(df["Sale price"], errors="coerce")
    df["Regular price"] = pd.to_numeric(df["Regular price"], errors="coerce")
    has_sale = df["Sale price"].notna()
    df["Variant Price"] = np.where(has_sale, df["Sale price"], df["Regular price"])
    df["Variant Compare At Price"] = np.where(has_sale, df["Regular price"], np.nan)
    missing = df["Variant Price"].isna().sum()
    if missing:
        warn(f"{missing} row(s) have no price; Variant Price left blank.")

    # 6. Inventory: track only rows that have a stock number
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce")
    has_stock = df["Stock"].notna()
    df["Variant Inventory Qty"] = df["Stock"]
    df["Variant Inventory Tracker"] = np.where(has_stock, "shopify", None)
    df["Variant Inventory Policy"] = np.where(has_stock, "deny", None)

    # 7. Categories -> leaf collection names
    if "Categories" in df.columns:
        df["Categories"] = df["Categories"].apply(leaf_categories)

    # 8. Weight unit and shipping (digital products don't ship)
    df["Variant Weight Unit"] = np.where(df["Weight (lbs)"].notna(), "lb", None)
    df["Variant Requires Shipping"] = ~df["Type"].str.contains("virtual|downloadable", na=False)

    # 9. Rename to Matrixify columns
    df = df.rename(columns={
        "Name": "Title", "Description": "Body HTML", "SKU": "Variant SKU",
        "Weight (lbs)": "Variant Weight",
        "Attribute 1 name": "Option1 Name", "Attribute 1 value(s)": "Option1 Value",
        "Attribute 2 name": "Option2 Name", "Attribute 2 value(s)": "Option2 Value",
        "Categories": "Custom Collections",
    })

    # 10. Options: no option name without a value
    for n in (1, 2):
        df.loc[df[f"Option{n} Value"].isna(), f"Option{n} Name"] = np.nan

    # 11. Images: first image on the product row, extra images on extra rows
    imgs = df["Images"].fillna("").apply(lambda s: [u.strip() for u in s.split(",") if u.strip()])
    df["Image Src"] = imgs.apply(lambda l: l[0] if l else np.nan)
    df["Image Position"] = np.where(df["Image Src"].notna(), 1, np.nan)
    extra = pd.DataFrame([
        {"Handle": h, "Command": "NEW", "Image Src": u, "Image Position": pos}
        for h, l in zip(df["Handle"], imgs) for pos, u in enumerate(l[1:], start=2)
    ])

    df["Command"] = "NEW"
    out = df[[c for c in MATRIXIFY_COLUMNS if c in df.columns]]
    out = pd.concat([out, extra], ignore_index=True)
    # keep every product's rows together
    return out.sort_values("Handle", kind="stable").reset_index(drop=True)[
        [c for c in MATRIXIFY_COLUMNS if c in out.columns]]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="sample_products.csv", help="WooCommerce product export (CSV)")
    p.add_argument("--output", default="matrixify_ready_products.xlsx", help="Output Excel file")
    args = p.parse_args()

    print(f"Reading {args.input} ...")
    result = convert(pd.read_csv(args.input))
    result.to_excel(args.output, index=False)
    print(f"Done: {len(result)} rows written to {args.output}")


if __name__ == "__main__":
    main()
