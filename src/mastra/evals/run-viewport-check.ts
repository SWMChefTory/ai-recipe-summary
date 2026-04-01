/**
 * StepViewportFit를 별도 프로세스로 실행하는 래퍼
 * stdin으로 steps JSON을 받고, stdout으로 결과 JSON을 출력
 *
 * 사용: echo '<steps json>' | npx tsx run-viewport-check.ts
 */
import { checkStepViewportFit } from "./step-viewport-check";

async function main() {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const steps = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
  const result = await checkStepViewportFit(steps);
  process.stdout.write(JSON.stringify(result));
}

main().catch((e) => {
  process.stderr.write(e.message);
  process.exit(1);
});
