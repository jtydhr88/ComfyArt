// #494-2 behavior harness: the input dialog / preset / handoff helpers through the real src/skills.ts, two different
// skills (poster, a synthetic brief-only skill; custom-workflow card removed — no Lovart card) + an old personal skill without inputs. No network, $0.
// #569: poster is now an effect skill (no presets), so the preset checks run on brand (template skill).
import { BUILTIN_SKILLS, hasSkillDialog, missingInputs, presetImage, skillDefaults, skillPreset, skillRunParams, withPreset } from '../../src/skills'
const by = (id: string) => BUILTIN_SKILLS.find((s) => s.id === id)!
const poster = by('poster-differentiated-compiler'), brand = by('brand-identity-director'), cw = { id: 'brief-only', name: 'Brief', instructions: 'Brief rules.', inputs: [{ key: 'brief', type: 'textarea' as const, required: true, label: { zh: '需求描述', en: 'Brief' } }] }
const old = { id: 'old-skill', name: 'Old', instructions: 'Old rules.', custom: true }
const r: Record<string, unknown> = {}
r.fields = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, (s.inputs ?? []).map((f) => [f.key, f.type, !!f.required, f.label.zh, f.label.en ?? null, f.placeholder?.en ?? null])]))
r.presets = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, (s.presets ?? []).map((p) => [p.id, p.name.en ?? null, !!p.prompt])]))
r.posterDefaults = skillDefaults(poster)
r.cwDefaults = skillDefaults(cw)
r.posterMissing = missingInputs(poster, skillDefaults(poster))
r.posterFilled = missingInputs(poster, { ...skillDefaults(poster), user_requirement: 'Autumn launch' })
r.brandDefaults = skillDefaults(brand)
r.brandMissing = missingInputs(brand, skillDefaults(brand))
r.brandFilled = missingInputs(brand, { ...skillDefaults(brand), brand_info: 'Wildpeak Coffee' })  // #748 Final: brand-identity-director template 1 (brand_info/subject_image/visual_direction)
r.posterPresets = poster.presets?.length ?? 0
r.cwMissing = missingInputs(cw, { brief: '  ' })
r.dialog = [hasSkillDialog(poster), hasSkillDialog(cw), hasSkillDialog(old), hasSkillDialog(brand)]
const second = brand.presets![1]
r.withPreset = withPreset(brand, second.id).instructions
r.brandInstr = brand.instructions
r.secondPrompt = second.prompt
r.withUnknown = withPreset(brand, 'nope').instructions === brand.instructions
r.withNull = withPreset(old, null) === old
r.presetDefault = skillPreset(brand)?.id
r.presetPick = skillPreset(brand, second.id)?.id
r.presetImg = presetImage(brand, second)
r.brandPresetImgs = brand.presets!.map((p) => presetImage(brand, p))
r.builtinPresetImgs = BUILTIN_SKILLS.flatMap((s) => (s.presets ?? []).map((p) => presetImage(s, p)))
r.posterNoPreset = skillRunParams(poster, { ...skillDefaults(poster), user_requirement: 'Autumn launch', user_image: '/view?f=a.png' }, null)
r.brandRun = skillRunParams(brand, { ...skillDefaults(brand), brand_info: 'Autumn launch', subject_image: '/view?f=a.png' }, second.id)
r.cwRun = skillRunParams(cw, { brief: 'Upscale my photo' }, null)
r.emptyRun = skillRunParams(old, {}, null)
console.log(JSON.stringify(r))
