/// <reference types="vite/client" />
import claude from '../assets/agents/claude-code.svg'
import qwen from '../assets/agents/qwen-code.svg'
import qwenDark from '../assets/agents/qwen-code-dark.svg'
import opencode from '../assets/agents/opencode.svg'
import opencodeDark from '../assets/agents/opencode-dark.svg'
import codex from '../assets/agents/codex.svg'
import gemini from '../assets/agents/gemini-cli.svg'
import deepseek from '../assets/agents/deepseek.svg'
import hermes from '../assets/agents/hermes.svg'
import hermesDark from '../assets/agents/hermes-dark.svg'
import { BUILTIN_AGENT } from '../bot'
import { Icons } from './icons'

// Official vendor logos, bundled locally and never recolored; sources in assets/agents/NOTICE.md.
const LOGOS: Record<string, [string, string?]> = { 'claude-code': [claude], 'qwen-code': [qwen, qwenDark], opencode: [opencode, opencodeDark], codex: [codex], 'gemini-cli': [gemini], 'deepseek-harness': [deepseek], hermes: [hermes, hermesDark] }

export function AgentLogo({ id }: { id: string }) {
  if (id === BUILTIN_AGENT) return <span className="ca-icon ca-agentlogo--loomi">{Icons.agent}</span>
  const l = LOGOS[id]
  if (!l) return <span className="ca-icon ca-agentlogo--generic">{Icons.cube}</span>
  return (
    <span className="ca-icon ca-agentlogo" data-id={id}>
      <img src={l[0]} alt="" width={16} height={16} className={l[1] ? 'ca-agentlogo__light' : undefined} />
      {l[1] && <img src={l[1]} alt="" width={16} height={16} className="ca-agentlogo__dark" />}
    </span>
  )
}
