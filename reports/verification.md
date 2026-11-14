# Pre-publication verification

- A rebuild in a project copy with empty data and report directories reproduced the existing 60,000-booking baseline. All 12 named SQLite analyses produced output.
- The full suite passed: 45 tests, including all four Streamlit pages, date/zone/service filters, empty results, and CSV generation.
- The regenerated Excel monthly sheet totals 60,000 requests, 52,198 completions, INR 17,211,937 in revenue and INR 10,058,501.88 in contribution before fixed costs. Automated checks verified the formulas; Excel recalculates them on opening.
- Chrome rendered charts on all four pages at 1440 x 1000 and downloaded the filtered bookings and hourly capacity CSVs. The README links to screenshots from that desktop run.
- Chrome also rendered all four pages and chart containers at a 390 x 844 viewport. Narrow captures are linked in the README.
- Fresh Python 3.14 virtual environment: installed requirements.txt and passed all 45 tests. Pandas 3.1.1 emitted three deprecation warnings for the weekday accessor.
