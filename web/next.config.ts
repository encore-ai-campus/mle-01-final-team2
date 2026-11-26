import type { NextConfig } from "next";

// standalone: Docker 이미지에 node_modules 전체 대신 실행에 필요한 파일만 담는다.
const config: NextConfig = { output: "standalone", reactStrictMode: true };

export default config;
