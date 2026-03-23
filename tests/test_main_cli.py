import importlib

import main as main_module
import parser_core


def _reload_main_with_patched_core(monkeypatch, fake_process_receipt, fake_save_to_excel):
    monkeypatch.setattr(parser_core, "process_receipt", fake_process_receipt)
    monkeypatch.setattr(parser_core, "save_to_excel", fake_save_to_excel)
    return importlib.reload(main_module)


def test_main_cli_processes_single_file(monkeypatch, tmp_path, sample_receipt_result):
    image_path = tmp_path / "one.jpg"
    image_path.write_bytes(b"fake-image")

    calls = {"process": 0, "save": 0}

    def fake_process(path):
        calls["process"] += 1
        assert path == str(image_path)
        return sample_receipt_result

    def fake_save(results, filename):
        calls["save"] += 1
        assert len(results) == 1
        assert filename == "receipts.xlsx"
        return filename

    main_reloaded = _reload_main_with_patched_core(monkeypatch, fake_process, fake_save)
    monkeypatch.setattr(main_reloaded.sys, "argv", ["main.py", str(image_path)])

    main_reloaded.main()

    assert calls["process"] == 1
    assert calls["save"] == 1


def test_main_cli_processes_directory(monkeypatch, tmp_path, sample_receipt_result):
    (tmp_path / "a.jpg").write_bytes(b"a")
    (tmp_path / "b.png").write_bytes(b"b")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")

    calls = {"process": 0, "save": 0}

    def fake_process(_):
        calls["process"] += 1
        return sample_receipt_result

    def fake_save(results, filename):
        calls["save"] += 1
        assert len(results) == 2
        assert filename == "receipts.xlsx"
        return filename

    main_reloaded = _reload_main_with_patched_core(monkeypatch, fake_process, fake_save)
    monkeypatch.setattr(main_reloaded.sys, "argv", ["main.py", str(tmp_path)])

    main_reloaded.main()

    assert calls["process"] == 2
    assert calls["save"] == 1


def test_main_cli_no_files_in_directory(monkeypatch, tmp_path, capsys):
    calls = {"save": 0}

    def fake_process(_):
        raise AssertionError("process_receipt should not be called when no files")

    def fake_save(results, filename):
        calls["save"] += 1
        return filename

    main_reloaded = _reload_main_with_patched_core(monkeypatch, fake_process, fake_save)
    monkeypatch.setattr(main_reloaded.sys, "argv", ["main.py", str(tmp_path)])

    main_reloaded.main()

    out = capsys.readouterr().out
    assert "Не найдено изображений" in out
    assert calls["save"] == 0
