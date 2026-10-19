# V3 validation scope

[中文](VALIDATION.md) · [User guide](USAGE.en.md)

Historical local acceptance as of 2026-10-19 combines different dates, networks and independent checks. It is not a simultaneous rerun or a guarantee for every article in a journal.

## Representative full-text checks passed

| Journal/platform | Scope and qualifications |
|---|---|
| Applied Energy | 3 Elsevier full-text XML samples using an entitled campus connection |
| Energy and Buildings, Building and Environment, Energy, Renewable and Sustainable Energy Reviews | 2 Elsevier XML samples each, same entitlement condition |
| Building Simulation | 2 PDF samples |
| Nature Communications | 3 OA XML samples |
| International Journal of Computer Vision | 2 XML/PDF samples |
| IEEE Access | 2 public PDFs, independent of the disabled API |
| TPAMI | 1 published version and 1 separately verified preprint, distinguished in records |
| CVPR, arXiv | 2 each, conference papers and preprints respectively |
| International Journal of Climatology | 1 OA PDF; subscription sample did not pass |
| PLOS Medicine, Frontiers in Energy Research, eLife | 2 each, including native-document conversion checks |
| Building Research & Information | 2 public PDFs, including article pagination/front-cover checks |
| Energies | 2 official-resource PDFs, checked against DOI and pagination |
| JMLR, PMLR | 2 and 1 samples; 1 actual Markdown conversion each |
| Science Advances, Copernicus/GMD | 2 each with actual XML-to-Markdown conversion |
| ACM, IOP, AIP, APS, ASCE | 1 each; not publisher-wide coverage |

Acquisition/completeness acceptance does not mean every sample was parsed by MinerU. The extension checks included six actual conversions: one JMLR, one PMLR, two Science Advances and two Copernicus samples. PDFs used MinerU API; native XML used the local renderer. This is not a claim of word-by-word manual verification.

## Blocked or incomplete

| Sample | Status |
|---|---|
| ACS `10.1021/acsenergylett.4c01233` | OA confirmed; official PDF still met browser verification |
| ACS `10.1021/acsenergylett.3c02406` | Non-OA; authorized full text unavailable |
| SAGE `10.1177/01436244211001497` | OA/repository located, access/certificate issues prevented verified PDF |
| ASME `10.1115/1.4072593` | OA, official PDF challenged |
| ASME `10.1115/1.4069386` | 23-page accepted manuscript identity/structure confirmed; independent completeness and 10-page published version not fully verified |
| OpenReview `i8tGb1ab1j` | Automated route 403; corresponding PMLR route passed independently |
| Nature Climate Change `10.1038/nclimate2841`, `10.1038/nclimate1580` | Subscription samples unavailable |
| Wiley `10.1002/joc.8834` | Full text unavailable |

Semantic Scholar/OSTI experimental routes were removed. Website challenges are not bypassed and TLS verification is not disabled. Main PDFs obtained separately can use the local-file input.

## Verification and reruns

Structured sources are checked for DOI, section/paragraph coverage, references and table values. PDFs separately require parseability, identity, reliable pagination or independent version comparison. Different manuscript/published page counts do not alone prove missing pages; apparently complete structure does not prove full completeness either.

An incorrect 169-page IOP candidate was rejected by title. A correct 67-page published text plus cover was subsequently compared with an independent institutional copy. AIP/ASCE/APS/IOP later completed published-version review; initial pending reports do not represent the final historical status.

Local `workspace/pdf_verifications.json` records are reused only when DOI and full SHA-256 match. They are excluded from source releases and are not inherited on new machines.

Historical root diagnostic CMDs were removed; developers may use `scripts/check_publishers.py` and `scripts/check_public_extensions.py`. These do not call MinerU/GPU by default; native XML can be rendered locally. Explicit `--parse-pdf` uses MinerU API and may consume credits.

Original reports remain under local `workspace` directories, not in GitHub. New machines need their own network/entitlement checks. Record failed, pending and accepted results separately.
