# Fixture provenance

`nist_excerpt.txt` is a **selected, manually transcribed browser excerpt**, not an unmodified recorded HTTP response. The official NIST CODATA 2022 bulk table was retrieved through the browser tool on 2026-10-08. Its electron mass and atomic mass constant rows were copied without changing scientific numbers. `nist_excerpt_metadata.json` hashes this excerpt and labels the capture `browser_excerpt`. NIST SRD 121 is the source; attribution and applicable SRD rights require review. The publication parser independently re-parses the stored excerpt. Neither checksum nor format validation certifies scientific truth.

Source: https://physics.nist.gov/cuu/Constants/Table/allascii.txt
Rights: https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications

`pubchem_synthetic.json` and `mp_synthetic.json` are **simulated protocol fixtures**, with deliberately arbitrary test values (42). They are not recorded live scientific observations, not verified reference data, and not authoritative material values. Tests always mark these captures `synthetic_fixture`. Publication rejects that origin. Simulated changed versions, conflicts and corrections in tests are not claimed as real source revisions.

Direct live API/bulk HTTP requests were attempted, but the execution proxy denied NIST and PubChem destinations; Materials Project had no credential. See `live_results.json`. Successful browser access to NIST does not establish that the automated HTTP connector succeeded. Replace/add fixtures with exact permitted API response captures once network access and source rights permit; retain the synthetic negative tests.
