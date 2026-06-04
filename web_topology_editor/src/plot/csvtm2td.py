from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

import chardet
import pandas as pd


def detectEncode(file_path: str | Path) -> str:
  path = Path(file_path)
  with path.open("rb") as f:
    detected = chardet.detect(f.read())
  return str(detected.get("encoding") or "utf-8")


def _load_json(path: Path) -> Dict[str, Dict[str, object]]:
  with path.open("r", encoding=detectEncode(path)) as f:
    data = json.load(f)
  if not isinstance(data, dict):
    raise ValueError("JSON 顶层必须为对象，格式应为 {obj: {tm: value}}")
  return data


def _default_output_path(input_path: Path, mode: str) -> Path:
  stem = input_path.stem
  suffix = input_path.suffix.lower()
  if mode == "json_to_pivot":
    return input_path.with_name(f"{stem}_pivot.csv")
  if mode == "pivot_to_json":
    return input_path.with_name(f"{stem}.json")
  if mode == "pivot_to_tidy":
    return input_path.with_name(f"{stem}_td.csv")
  if mode == "tidy_to_pivot":
    return input_path.with_name(f"{stem}_pivot.csv")
  if suffix == ".json":
    return input_path.with_name(f"{stem}.csv")
  return input_path.with_name(f"{stem}_out.csv")


def json_to_pivot(input_path: str | Path, output_path: Optional[str | Path] = None, time_column: str = "tm") -> Path:
  src = Path(input_path)
  dst = Path(output_path) if output_path else _default_output_path(src, "json_to_pivot")
  data = _load_json(src)
  if not data:
    raise ValueError("JSON 内容为空")

  all_timestamps = []
  seen = set()
  for _, ts_map in data.items():
    if isinstance(ts_map, dict):
      for t in ts_map.keys():
        ts = str(t)
        if ts not in seen:
          seen.add(ts)
          all_timestamps.append(ts)
  if not all_timestamps:
    raise ValueError("JSON 中未识别到时间序列键")

  rows = []
  for ts in all_timestamps:
    row = {time_column: ts}
    for obj, ts_map in data.items():
      value = None
      if isinstance(ts_map, dict):
        value = ts_map.get(ts)
      row[str(obj)] = value
    rows.append(row)

  df = pd.DataFrame(rows)
  dst.parent.mkdir(parents=True, exist_ok=True)
  df.to_csv(dst, index=False, encoding="utf-8-sig")
  return dst


def pivot_to_json(input_path: str | Path, output_path: Optional[str | Path] = None, time_column: str = "tm") -> Path:
  src = Path(input_path)
  dst = Path(output_path) if output_path else _default_output_path(src, "pivot_to_json")
  df = pd.read_csv(src, encoding=detectEncode(src))
  if df.empty:
    raise ValueError("输入 pivot 文件为空")
  if time_column not in df.columns:
    time_column = str(df.columns[0])

  data: Dict[str, Dict[str, object]] = {}
  for col in df.columns:
    if col == time_column:
      continue
    obj_map: Dict[str, object] = {}
    for _, row in df[[time_column, col]].iterrows():
      tm = str(row[time_column]) if pd.notna(row[time_column]) else ""
      if not tm:
        continue
      value = row[col]
      obj_map[tm] = None if pd.isna(value) else value
    data[str(col)] = obj_map

  dst.parent.mkdir(parents=True, exist_ok=True)
  dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
  return dst


def pivot_to_tidy(
  input_path: str | Path,
  output_path: Optional[str | Path] = None,
  time_column: str = "tm",
  obj_column: str = "obj",
  value_column: str = "value",
) -> Path:
  src = Path(input_path)
  dst = Path(output_path) if output_path else _default_output_path(src, "pivot_to_tidy")
  df = pd.read_csv(src, encoding=detectEncode(src))
  if df.empty:
    raise ValueError("输入 pivot 文件为空")
  if time_column not in df.columns:
    time_column = str(df.columns[0])

  value_cols = [c for c in df.columns if c != time_column]
  if not value_cols:
    raise ValueError("pivot 文件缺少对象列")

  tidy = df.melt(
    id_vars=[time_column],
    value_vars=value_cols,
    var_name=obj_column,
    value_name=value_column,
  )
  tidy = tidy.rename(columns={time_column: "tm"})
  if obj_column != "obj":
    tidy = tidy.rename(columns={obj_column: "obj"})
  if value_column != "value":
    tidy = tidy.rename(columns={value_column: "value"})

  dst.parent.mkdir(parents=True, exist_ok=True)
  tidy.to_csv(dst, index=False, encoding="utf-8-sig")
  return dst


def tidy_to_pivot(
  input_path: str | Path,
  output_path: Optional[str | Path] = None,
  time_column: str = "tm",
  obj_column: str = "obj",
  value_column: str = "value",
) -> Path:
  src = Path(input_path)
  dst = Path(output_path) if output_path else _default_output_path(src, "tidy_to_pivot")
  df = pd.read_csv(src, encoding=detectEncode(src))
  if df.empty:
    raise ValueError("输入 tidy 文件为空")

  required = [time_column, obj_column, value_column]
  missing = [c for c in required if c not in df.columns]
  if missing:
    raise ValueError(f"tidy 文件缺少列: {', '.join(missing)}")

  pivot_df = df.pivot_table(
    index=time_column,
    columns=obj_column,
    values=value_column,
    aggfunc="first",
  ).reset_index()
  pivot_df.columns.name = None

  dst.parent.mkdir(parents=True, exist_ok=True)
  pivot_df.to_csv(dst, index=False, encoding="utf-8-sig")
  return dst


def convert_file_format(
  input_path: str | Path,
  mode: str,
  output_path: Optional[str | Path] = None,
  time_column: str = "tm",
  obj_column: str = "obj",
  value_column: str = "value",
) -> Path:
  mode_key = str(mode or "").strip().lower()
  if mode_key == "json_to_pivot":
    return json_to_pivot(input_path, output_path=output_path, time_column=time_column)
  if mode_key == "pivot_to_json":
    return pivot_to_json(input_path, output_path=output_path, time_column=time_column)
  if mode_key == "pivot_to_tidy":
    return pivot_to_tidy(
      input_path,
      output_path=output_path,
      time_column=time_column,
      obj_column=obj_column,
      value_column=value_column,
    )
  if mode_key == "tidy_to_pivot":
    return tidy_to_pivot(
      input_path,
      output_path=output_path,
      time_column=time_column,
      obj_column=obj_column,
      value_column=value_column,
    )
  raise ValueError(f"不支持的转换模式: {mode}")


def csvtm2td(file_path: str | Path) -> Path:
  return pivot_to_tidy(file_path)


def json2csv_td(dirpath: str, filename: str) -> Path:
  src = Path(dirpath) / filename
  pivot_path = json_to_pivot(src)
  return pivot_to_tidy(pivot_path)


def json2csvtm(dirpath: str, filename: str) -> Path:
  src = Path(dirpath) / filename
  return json_to_pivot(src)


def _main() -> int:
  parser = argparse.ArgumentParser(description="CSV/JSON 时序数据格式转换工具")
  parser.add_argument("--input", required=True, help="输入文件路径")
  parser.add_argument("--mode", required=True, choices=["json_to_pivot", "pivot_to_json", "pivot_to_tidy", "tidy_to_pivot"], help="转换模式")
  parser.add_argument("--output", default="", help="输出文件路径（可选）")
  parser.add_argument("--time-column", default="tm", help="时间列名")
  parser.add_argument("--obj-column", default="obj", help="对象列名（tidy 相关）")
  parser.add_argument("--value-column", default="value", help="值列名（tidy 相关）")
  args = parser.parse_args()

  out = convert_file_format(
    input_path=args.input,
    mode=args.mode,
    output_path=(args.output or None),
    time_column=args.time_column,
    obj_column=args.obj_column,
    value_column=args.value_column,
  )
  print(str(out))
  return 0


if __name__ == "__main__":
  raise SystemExit(_main())