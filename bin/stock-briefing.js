#!/usr/bin/env node

const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const PYTHON = "/opt/anaconda3/bin/python3";
const SCRIPTS_DIR = path.join(__dirname, "..", "scripts");
const DATA_DIR = path.join(os.homedir(), ".stock-briefing", "data");

const COMMANDS = {
  setup: "setup_profile.py",
  run: "daily_briefing.py",
  alert: "alert_check.py",
};

function printHelp() {
  console.log(`
stock-briefing — 투자 성향 맞춤 일일 주식 브리핑 CLI

사용법:
  stock-briefing setup    투자 프로필 & 관심 종목 설정 (최초 1회)
  stock-briefing run      일일 브리핑 실행 (기술적 지표 + 뉴스 + AI 시그널)
  stock-briefing alert    급변 알림 체크 (±threshold% 감지)

옵션:
  --help, -h              이 도움말 표시
  --version, -v           버전 표시

환경변수:
  UPSTAGE_API_KEY         Upstage Solar Pro 3 API 키 (AI 시그널에 필요)
                          https://console.upstage.ai 에서 발급

예시:
  export UPSTAGE_API_KEY=your_key_here
  stock-briefing setup
  stock-briefing run
  stock-briefing alert
`);
}

function checkPython() {
  if (!fs.existsSync(PYTHON)) {
    console.error(`오류: Python을 찾을 수 없습니다: ${PYTHON}`);
    console.error(
      "Anaconda가 설치되어 있지 않다면 --python 옵션으로 경로를 지정하거나"
    );
    console.error("환경변수 STOCK_BRIEFING_PYTHON 에 Python 경로를 설정하세요.");
    process.exit(1);
  }
}

function runScript(scriptFile) {
  checkPython();
  const scriptPath = path.join(SCRIPTS_DIR, scriptFile);

  if (!fs.existsSync(scriptPath)) {
    console.error(`오류: 스크립트를 찾을 수 없습니다: ${scriptPath}`);
    process.exit(1);
  }

  const pythonBin =
    process.env.STOCK_BRIEFING_PYTHON || PYTHON;

  const child = spawn(pythonBin, [scriptPath], {
    stdio: "inherit",
    env: {
      ...process.env,
      STOCK_BRIEFING_DATA_DIR: process.env.STOCK_BRIEFING_DATA_DIR || DATA_DIR,
    },
  });

  child.on("exit", (code) => {
    process.exit(code ?? 0);
  });

  child.on("error", (err) => {
    console.error(`실행 오류: ${err.message}`);
    process.exit(1);
  });
}

// --- main ---
const args = process.argv.slice(2);
const cmd = args[0];

if (!cmd || cmd === "--help" || cmd === "-h") {
  printHelp();
  process.exit(0);
}

if (cmd === "--version" || cmd === "-v") {
  const pkg = require("../package.json");
  console.log(`stock-briefing-cli v${pkg.version}`);
  process.exit(0);
}

const scriptFile = COMMANDS[cmd];
if (!scriptFile) {
  console.error(`알 수 없는 커맨드: ${cmd}`);
  console.error('stock-briefing --help 로 사용법을 확인하세요.');
  process.exit(1);
}

runScript(scriptFile);
