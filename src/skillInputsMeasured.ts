/** #748 — data-driven right panel: inputs[] for the 16 reference skills come from the product's reference measure
 *  (src/data/skill-inputs-748.json, #748 comment 6646601205).
 *  Example-class → upload + additional (Start enabled); template-class → 当前模板 + requireds (Start disabled until filled).
 *  The measure is zh-only; English labels are carried by zh label below (TODO(#748): swap for en measure). */
import measured from './data/skill-inputs-748.json'
import type { SkillInput } from './skills'

interface MeasuredField { key: string; type: 'upload' | 'text'; label_zh: string; required?: boolean; placeholder_zh?: string; maxlength?: number }
interface MeasuredSkill { inputs: MeasuredField[]; currentTemplate?: boolean; startDisabledWhenEmpty?: boolean }

/** zh → en copy (reference en page not yet measured). Example-class en keeps #687 reference-card copy. */
const EN: Record<string, string> = {
  上传文件: 'Upload Files', 补充描述: 'Additional Details', '有什么想补充的吗？': 'Anything else to add?',
  商品与包装资料: 'Product & packaging info', 商品与包装素材: 'Product & packaging assets', 视觉呈现方式: 'Visual presentation',
  静态原稿: 'Static artwork', 动态要求: 'Motion requirements',
  商品图片: 'Product images', 商品资料: 'Product info', '品牌素材（选填）': 'Brand assets (optional)', 补充要求: 'Additional requirements',
  品牌资料: 'Brand info', 品牌素材: 'Brand assets',
}
/** example-class runtime keys stay `file` / `note` (#687 tests + saved drafts). */
const KEY: Record<string, string> = { upload: 'file', notes: 'note' }

function toInput(f: MeasuredField): SkillInput {
  const ph = f.placeholder_zh
  return {
    key: KEY[f.key] ?? f.key,
    label: { zh: f.label_zh, ...(EN[f.label_zh] ? { en: EN[f.label_zh] } : {}) },
    type: f.type === 'upload' ? 'image' : f.key === 'notes' ? 'textarea' : 'text', // example-class 补充描述 stays the multi-line box
    ...(f.required ? { required: true } : {}),
    ...(ph ? { placeholder: { zh: ph, en: EN[ph] ?? ph /* TODO(#748): en measure */ } } : {}),
    ...(f.maxlength ? { maxLength: f.maxlength } : {}),
  }
}

const SKILLS = (measured as { skills: Record<string, MeasuredSkill> }).skills
export const MEASURED_INPUTS_748: Record<string, SkillInput[]> =
  Object.fromEntries(Object.entries(SKILLS).map(([id, s]) => [id, s.inputs.map(toInput)]))
export const MEASURED_TEMPLATE_CLASS_748: ReadonlySet<string> =
  new Set(Object.entries(SKILLS).filter(([, s]) => s.startDisabledWhenEmpty).map(([id]) => id))
