import { BUILTIN_SKILLS, isSkillMediaVideo, matchesSkillChip, skillChips, skillCover, skillCoverVideoHover, skillVideo, SKILL_VIDEO_PENDING_NEW6 } from '../../src/skills'
const r: Record<string, unknown> = {}
const old = { id: 'old-skill', name: 'o', instructions: '', custom: true }
r.noImage = skillCover(old)
r.ownImage = skillCover({ ...old, images: { 'r.png': 'input/r.png' } })
r.custom = skillCover(BUILTIN_SKILLS.find((s) => s.id === 'interior')!)
r.customNoCover = skillCover({ ...BUILTIN_SKILLS.find((s) => s.id === 'interior')!, cover: undefined }) // #581: fallback still null
r.builtinCovers = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillCover(s)?.src ?? null]))
r.chips = skillChips(BUILTIN_SKILLS)
r.byChip = Object.fromEntries((r.chips as string[]).map((c) => [c, BUILTIN_SKILLS.filter((s) => matchesSkillChip(s, c as never)).map((s) => s.id)]))
// #529 — video field data-driven (mutation: drop video → null; custom never fakes a badge)
r.builtinVideos = Object.fromEntries(BUILTIN_SKILLS.map((s) => [s.id, skillVideo(s)]))
r.noVideo = skillVideo(old)
r.customVideo = skillVideo({ ...old, cover: undefined })
r.videoMutated = skillVideo({ ...BUILTIN_SKILLS.find((s) => s.id === 'poster')!, video: undefined })
// #575 — media detector + hover contract + pending new6 + thumbnail/banner example lead mp4
r.isVideo = {
  mp4: isSkillMediaVideo('https://x.test/a.mp4'),
  webm: isSkillMediaVideo('https://x.test/a.webm?x=1'),
  mov: isSkillMediaVideo('https://x.test/a.mov#t=0'),
  webp: isSkillMediaVideo('https://x.test/a.webp'),
  empty: isSkillMediaVideo(''),
  undef: isSkillMediaVideo(undefined),
}
r.pendingNew6 = [...SKILL_VIDEO_PENDING_NEW6]
r.thumbEx = BUILTIN_SKILLS.find((s) => s.id === 'thumbnail')!.examples
r.bannerEx = BUILTIN_SKILLS.find((s) => s.id === 'banner')!.examples
r.motionPresetVideos = (BUILTIN_SKILLS.find((s) => s.id === 'motion')!.presets ?? []).map((p) => p.video ?? null)
// hover: enter plays; leave pauses + seeks 0; null is no-op
const calls: string[] = []
const fake = {
  play: () => { calls.push('play'); return Promise.resolve() },
  pause: () => { calls.push('pause') },
  currentTime: 9,
} as unknown as HTMLVideoElement
skillCoverVideoHover(null, 'enter')
skillCoverVideoHover(fake, 'enter')
skillCoverVideoHover(fake, 'leave')
r.hoverCalls = calls
r.hoverSeek = fake.currentTime
console.log(JSON.stringify(r))
