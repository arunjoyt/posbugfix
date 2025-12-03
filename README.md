Update on 03-Dec-2025: 

This is fixed in ERPNext v15.91.0 via https://github.com/frappe/erpnext/pull/50558

So the workaround done in this app by overiding a whitelisted method is no longer needed.

Earlier: 
### POSBugFix

Contains bugs fixes for EPRNext POS

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app posbugfix
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/posbugfix
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
