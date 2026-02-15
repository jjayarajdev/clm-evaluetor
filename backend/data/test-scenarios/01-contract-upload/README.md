# 01 - Contract Upload Testing

## Purpose
Test basic contract upload and document parsing functionality.

## Documents
| File | Type | Pages | Description |
|------|------|-------|-------------|
| `NDA_NYU_Stern.pdf` | NDA | 2 | Simple 2-page NDA - ideal for quick upload tests |

## Functionality Tested
- File upload via API
- PDF text extraction
- Document type detection
- Initial processing pipeline

## Test Workflow

### 1. Upload Contract
```bash
# Get auth token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' | jq -r '.access_token')

# Upload the NDA
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@NDA_NYU_Stern.pdf"
```

### 2. Verify Upload
```bash
# List contracts to verify upload
curl http://localhost:8000/api/contracts \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Check Processing Status
```bash
# Get contract details (replace {contract_id} with actual ID)
curl http://localhost:8000/api/contracts/{contract_id} \
  -H "Authorization: Bearer $TOKEN"
```

## Expected Results
- Upload returns 201 with contract ID
- Contract status progresses: `uploaded` -> `processing` -> `processed`
- Raw text is extracted from PDF
- Document type detected as "NDA"

## Success Criteria
- [ ] File uploads without error
- [ ] Contract record created in database
- [ ] Text extraction completes
- [ ] No timeout or memory errors
