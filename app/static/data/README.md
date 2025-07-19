# Bank Logos

This directory contains static data files for the bank account form.

## bank_logos.json

This file contains the mapping of bank codes to their logo URLs. Logos come from two sources:
1. **QPay API** - External URLs from QPay's logo service
2. **Local assets** - Local files stored in `/static/assets/bank_logos/`

### Structure
```json
{
  "050000": "https://qpay.mn/q/logo/khanbank.png",
  "150000": "/static/assets/bank_logos/golomt_bank.png",
  "020000": "/static/assets/bank_logos/capital_bank.jpg",
  ...
}
```

### Updating Logos

To update the bank logos, run the fetch script from the project root:

```bash
python fetch_bank_logos.py
```

This will:
1. Make a dummy QPay invoice request
2. Extract bank logos from the response
3. Update this JSON file with the latest logo URLs

### Note
The logos are fetched once and stored statically to avoid making QPay requests on every page load.