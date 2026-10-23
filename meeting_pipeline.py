import argparse
import sys
from pathlib import Path

from pipeline.aligner import assign_speakers, chunk_subtitles
from pipeline.asr import transcribe_words
from pipeline.audio import SUPPORTED_EXTENSIONS, normalized_audio_wav
from pipeline.diarization import diarize_speakers
from pipeline.exporters import export_srt, export_transcript_md
from pipeline.outputs import allocate_output_set, summary_path_for
from pipeline.speakers import parse_display_names, unknown_labels
from pipeline.summarizer import generate_meeting_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mac 本機會議錄音轉字幕、逐字稿與會議總結")
    parser.add_argument("audio_path", nargs="?", type=Path, help="會議錄音（.m4a/.mp3/.mp4/.wav）")
    parser.add_argument("--summarize-only", type=Path, metavar="TRANSCRIPT", help="只根據既有逐字稿重新產生會議總結")
    parser.add_argument("--num-speakers", type=int)
    parser.add_argument("--min-speakers", type=int)
    parser.add_argument("--max-speakers", type=int)
    parser.add_argument("--speakers", help='顯示名稱，例如 "SPEAKER_00=王經理,SPEAKER_01=李工程師"')
    parser.add_argument("--agy-model")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--hf-token")
    parser.add_argument("--no-summary", action="store_true", help="不呼叫 agy，逐字稿不離開本機")
    args = parser.parse_args(argv)

    if (args.audio_path is None) == (args.summarize_only is None):
        parser.error("必須擇一提供 audio_path 或 --summarize-only")
    if args.summarize_only is not None:
        audio_only = [args.num_speakers, args.min_speakers, args.max_speakers, args.speakers, args.output_dir, args.hf_token]
        if args.no_summary or any(v is not None for v in audio_only):
            parser.error("--summarize-only 只能搭配 --agy-model")
    else:
        if args.audio_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            parser.error(f"不支援的錄音格式：{args.audio_path.suffix}（支援 {', '.join(sorted(SUPPORTED_EXTENSIONS))}）")
        if not args.audio_path.is_file():
            parser.error(f"找不到錄音：{args.audio_path}")
    if args.num_speakers is not None and (args.min_speakers is not None or args.max_speakers is not None):
        parser.error("--num-speakers 不可與 --min-speakers/--max-speakers 併用")
    for value in (args.num_speakers, args.min_speakers, args.max_speakers):
        if value is not None and value < 1:
            parser.error("說話者人數必須 >= 1")
    if args.min_speakers is not None and args.max_speakers is not None and args.min_speakers > args.max_speakers:
        parser.error("--min-speakers 不可大於 --max-speakers")
    try:
        args.display_names = parse_display_names(args.speakers)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run_pipeline(args: argparse.Namespace) -> int:
    if args.summarize_only is not None:
        transcript = args.summarize_only
        if not transcript.is_file():
            _log(f"找不到逐字稿：{transcript}")
            return 1
        ok = generate_meeting_summary(transcript, summary_path_for(transcript), agy_model=args.agy_model)
        return 0 if ok else 1

    output_dir = args.output_dir or args.audio_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = allocate_output_set(output_dir, args.audio_path.stem)

    _log("[1/4] 正規化音訊")
    with normalized_audio_wav(args.audio_path) as wav_path:
        _log("[2/4] 語音辨識（mlx-whisper）")
        words = transcribe_words(wav_path)
        _log("[2/4] 說話者辨識（pyannote）")
        turns = diarize_speakers(
            wav_path,
            hf_token=args.hf_token,
            num_speakers=args.num_speakers,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
        )

    _log("[3/4] 對齊與匯出")
    cues = chunk_subtitles(assign_speakers(words, turns))
    for label in unknown_labels(args.display_names, {cue.speaker for cue in cues}):
        _log(f"警告：--speakers 指定的 {label} 不存在於本次錄音的說話者標籤中，已忽略")
    export_srt(cues, outputs.srt, args.display_names)
    export_transcript_md(cues, outputs.transcript, args.display_names)
    _log(f"已輸出 {outputs.srt}\n已輸出 {outputs.transcript}")

    if args.no_summary:
        return 0
    _log("[4/4] 會議總結（agy）")
    ok = generate_meeting_summary(outputs.transcript, outputs.summary, agy_model=args.agy_model)
    if ok:
        _log(f"已輸出 {outputs.summary}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    return run_pipeline(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
