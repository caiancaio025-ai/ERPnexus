from pathlib import Path


WEB_ROOT = Path("/web")
LAB_DASHBOARD = WEB_ROOT / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"


def _source() -> str:
    return LAB_DASHBOARD.read_text(encoding="utf-8")


def test_detail_tabs_persist_pending_edits_before_navigation() -> None:
    source = _source()

    assert "async function switchDetailTab(nextTab: DetailTab)" in source
    assert "const hadPendingChanges = hasDetailChanges(detail);" in source
    assert "const savedDetail = await persistDetail(detail, false);" in source
    assert "if (!savedDetail) return;" in source
    assert "setDetailTab(nextTab);" in source
    assert 'onTab={(nextTab) => void switchDetailTab(nextTab)}' in source
    assert 'onClick={() => onTab("general")}' in source
    assert 'onClick={() => onTab("technical")}' in source
    assert 'onClick={() => onTab("status")}' in source
    assert 'onClick={() => setTab("general")}' not in source


def test_status_and_substatus_use_the_version_returned_by_autosave() -> None:
    source = _source()

    assert source.count("if (hasDetailChanges(currentDetail))") >= 2
    assert source.count("const savedDetail = await persistDetail(currentDetail, false);") >= 2
    assert "status: targetStatus, version: currentDetail.version" in source
    assert "active, version: currentDetail.version" in source
    assert "detailSavedFingerprintRef.current = detailFingerprint(updatedDetail, canViewValues);" in source


def test_closing_detail_saves_pending_changes_and_save_failures_keep_modal_open() -> None:
    source = _source()

    assert "async function closeDetail()" in source
    assert "if (hasDetailChanges(detail))" in source
    assert "const savedDetail = await persistDetail(detail, false);" in source
    assert "if (!savedDetail) return;" in source
    assert "setDetail(null);" in source
    assert 'onClose={() => void closeDetail()}' in source


def test_autosave_tracks_server_fingerprint_and_avoids_redundant_patch() -> None:
    source = _source()

    assert "const detailSavedFingerprintRef = useRef<string | null>(null);" in source
    assert "const detailSavePromiseRef = useRef<Promise<DetailState | null> | null>(null);" in source
    assert "if (detailSavedFingerprintRef.current === currentFingerprint)" in source
    assert "if (detailSavePromiseRef.current) return detailSavePromiseRef.current;" in source
    assert "detailSavedFingerprintRef.current = detailFingerprint(savedDetail, canViewValues);" in source
    assert "return JSON.stringify(payloadFromForm(detail, includeSensitiveValues));" in source
