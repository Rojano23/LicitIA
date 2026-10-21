# Camelot physical table dependency record

- Distribution: **camelot-py==2.0.0**; import `camelot` (not the unrelated camelot package).
- Repository/license: https://github.com/camelot-dev/camelot/blob/v2.0.0/LICENSE — MIT.
- Benchmark used Python3.13 on macOSarm64; product spike uses the same Python ABI.
- Configuration: lattice/combined, pdfium, resolution300; backend fallback disabled
  explicitly so a missing PDFium backend fails closed instead of selecting a system
  tool. This does not change lattice's table parameters; no ML/OCR extras.
- Material runtime dependencies declared by Camelot: playa-pdf (MIT), OpenCV headless
  (Apache-2.0), pypdfium2/PDFium (BSD/Apache plus bundled third-party notices),
  numpy/pandas/openpyxl (permissive BSD/MIT), click/tabulate/et-xmlfile.
  Exact resolved versions are captured in the spike report and future freeze map.
- Ghostscript is not required for the selected PDFium path and is not installed as
  an integration dependency. No pdfplumber, PaddleOCR, docTR, neural backend or model
  weights are added. Existing OCR dependencies are outside this change.
- License evidence: backend/reports/table_tooling_benchmark/licenses/ and
  installed_dependency_licenses.json contain the verified upstream snapshots and
  runtime metadata used in architectural acceptance. MIT permits commercial use
  subject to notice/license preservation; no mandatory commercial license was
  identified for the selected path. Ship the relevant PDFium/transitive notices
  with redistributed binaries and review the actual build/package contents.
- No legal guarantee is provided. Unreviewed optional backends/model weights or
  different binary distributions are not covered by this assessment. Existing
  product dependencies retain their independent licensing obligations.

Native is the quotation authority; Camelot's MIT license and parser confidence do
not confer contractual authority on its extracted text. See ADR0018.
