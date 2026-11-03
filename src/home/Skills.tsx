import { showMemoryToast } from '../memory'
/** #460 G1 — Skills Explore / Favourites / Personal shell (#494: cards driven by the built-in skill data). */
import { useEffect, useMemo, useRef, useState } from 'react'

import { thumbUrl } from '../comfy'
import { t } from '../i18n'
import { newProject } from '../projects'
import {
  hasSkillDialog,
  importLanding,
  loadFavourites,
  loadSkillUsage,
  loadSkills,
  recordSkillUse,
  skillDescription,
  skillAuthor,
  skillChips,
  skillCover,
  skillCoverVideoHover,
  skillQuickStartCoverFit,
  skillVideo,
  matchesSkillChip,
  toggleFavourite,
  type Skill,
  type SkillChipId,
} from '../skills'
import { BRAND } from '../brand'
import { Icons } from '../ui/icons'
import { SkillImportDialog } from '../ui/SkillImportDialog'
import { openSkillEditor, skillsOpenAtom } from '../ui/SkillsDialog'
import { SkillRunDialog } from '../ui/SkillRunDialog'

type Tab = 'explore' | 'favourites' | 'personal'
export const CHIP_LABEL: Record<SkillChipId, string> = {
  forYou: 'home.skillsForYou',
  ecommerce: 'home.skillsChipEcommerce',
  branding: 'home.skillsChipBranding',
  social: 'home.skillsChipSocial',
  website: 'home.skillsChipWebsite',
  ads: 'home.skillsChipAds',
}

/** #494/#581 — Explore/Favourites card: 231:173 cover, image badge, title, description, author + real usage when >0.
 *  #494-2: cover / title / hover 「试用此技能」 all call onTry (the skill's own dialog, or main's direct start).
 *  Favorite **count** is never shown (membership-only store); cover bookmark toggle stays.
 *  Personal tab reuses this with layout="row": square cover left, title + one-line description right, no author. */
function SkillWallCard({
  skill, fav, onFav, onTry, usage = 0, layout = 'wall',
}: {
  skill: Skill
  fav: boolean
  onFav: () => void
  onTry: () => void
  usage?: number
  layout?: 'wall' | 'row'
}) {
  const cover = skillCover(skill)
  const videoSrc = skillVideo(skill)
  const author = skillAuthor(skill)
  const src = cover && (cover.own === 'bundled' ? cover.src : thumbUrl(cover.src, 512))
  const desc = skillDescription(skill)
  // #494 — a cover that fails to load falls back to the same placeholder; keyed by src so a new src retries.
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const showImg = !!src && failedSrc !== src
  const row = layout === 'row'
  const kind = videoSrc ? 'video' : 'image'
  const playVideo = () => skillCoverVideoHover(videoRef.current, 'enter')
  const stopVideo = () => skillCoverVideoHover(videoRef.current, 'leave')
  return (
    <article
      className={row ? 'ca-swall__card ca-swall__card--row' : 'ca-swall__card'}
      data-testid="skills-wall-card"
      data-skill={skill.id}
      data-custom={skill.custom || undefined}
      data-layout={layout}
      data-has-video={videoSrc ? '1' : undefined}
      onClick={row ? onTry : undefined}
      onMouseEnter={videoSrc && !row ? playVideo : undefined}
      onMouseLeave={videoSrc && !row ? stopVideo : undefined}
      onFocus={videoSrc && !row ? playVideo : undefined}
      onBlur={videoSrc && !row ? stopVideo : undefined}
    >
      <div className="ca-swall__cover" data-fit={skillQuickStartCoverFit(skill)} role="button" tabIndex={0} aria-label={skill.name} onClick={row ? undefined : onTry}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onTry() } }}>
        {showImg
          ? <img src={src} alt={skill.name} loading="lazy" data-testid="skills-card-cover" onError={() => setFailedSrc(src)} />
          : <span className="ca-swall__placeholder" data-testid="skills-card-placeholder"><span className="ca-icon">{Icons.skill}</span></span>}
        {videoSrc && !row && (
          <video
            ref={videoRef}
            className="ca-swall__video"
            src={videoSrc}
            muted
            loop
            playsInline
            preload="metadata"
            data-testid="skills-card-video"
            aria-hidden="true"
          />
        )}
        {!row && <span className="ca-swall__badge" data-testid="skills-card-kind" data-kind={kind} aria-hidden="true"><span className="ca-icon">{kind === 'video' ? Icons.videoLine : Icons.imageLine}</span></span>}
        {!row && (
          <>
            <button
              type="button"
              className="ca-swall__bookmark"
              data-testid="skills-card-bookmark"
              data-on={fav || undefined}
              aria-pressed={fav}
              title={fav ? t('home.skillsUnfavourite') : t('home.skillsFavourite')}
              onClick={(e) => { e.stopPropagation(); onFav() }}
            >
              <span className="ca-icon">{fav ? Icons.bookmarkFilled : Icons.bookmark}</span>
            </button>
            <button
              type="button"
              className="ca-swall__try"
              data-testid="skills-card-try"
              onClick={(e) => { e.stopPropagation(); onTry() }}
            >
              {t('home.skillsTryThis')}
            </button>
          </>
        )}
      </div>
      <div className="ca-swall__meta">
        <h3 className="ca-swall__title" onClick={row ? undefined : onTry}>{skill.name}</h3>
        <p className="ca-swall__desc">{desc}</p>
        {!row && (
          <div className="ca-swall__author" data-testid="skills-card-author" data-kind={author.kind}>
            {author.kind === 'builtin'
              ? <img className="ca-swall__avatar" src={BRAND.logoPath} alt="" aria-hidden="true" />
              : <span className="ca-swall__avatar" aria-hidden="true"><span className="ca-icon">{Icons.user}</span></span>}
            <span className="ca-swall__author-name">{author.label}</span>
            {usage > 0 && (
              <span className="ca-swall__stat" data-testid="skills-card-usage" title={t('home.skillsUsage', usage)}>
                <span className="ca-icon" aria-hidden="true">{Icons.play}</span>
                {t('home.skillsUsageShort', usage)}
              </span>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

export function Skills() {
  const [tab, setTab] = useState<Tab>('explore')
  const [chip, setChip] = useState<SkillChipId>('forYou')
  const [skills, setSkills] = useState<Skill[]>([])
  const [favs, setFavs] = useState<string[]>(() => loadFavourites())
  const [usageMap, setUsageMap] = useState<Record<string, number>>(() => loadSkillUsage())

  const [menu, setMenu] = useState(false)
  const [importing, setImporting] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const [running, setRunning] = useState<{ id: string; preset: string | null } | null>(null)
  /** #494-2 — a card opens the skill's OWN dialog when its data has inputs[]; legacy skills keep main's direct start. */
  /** #581 — direct (no-dialog) starts also record a real local usage bump. */
  const startDirect = (s: Skill) => { recordSkillUse(s.id); setUsageMap(loadSkillUsage()); newProject({ skill: s.id }) }
  const tryCard = (s: Skill) => (hasSkillDialog(s) ? setRunning({ id: s.id, preset: null }) : startDirect(s))

  useEffect(() => { void loadSkills().then(setSkills) }, [])
  useEffect(() => {
    if (!menu) return
    const off = (e: PointerEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(false) }
    window.addEventListener('pointerdown', off)
    return () => window.removeEventListener('pointerdown', off)
  }, [menu])

  const personal = useMemo(() => skills.filter((s) => s.custom), [skills])
  /** #494-2 / #489 — 「你创建的」 = imported or hand-made; 「Loomi 创建的」 = the same learned[] store #465 uses. */
  const yours = useMemo(() => personal.filter((s) => !s.learned), [personal])
  const loomi = useMemo(() => personal.filter((s) => !!s.learned), [personal])
  const explore = useMemo(() => skills.filter((s) => !s.custom), [skills])
  /** #494 — chips come from data; a category with no skill (today: 网站) is not shown. */
  const chips = useMemo(() => skillChips(explore), [explore])
  const favouriteSkills = useMemo(() => skills.filter((s) => favs.includes(s.id)), [skills, favs])

  const wall = useMemo(() => {
    if (tab === 'favourites') return favouriteSkills
    if (tab === 'personal') return personal
    return explore.filter((s) => matchesSkillChip(s, chip))
  }, [tab, chip, explore, personal, favouriteSkills])

  const emptyKey = tab === 'favourites'
    ? 'home.skillsEmptyFavourites'
    : tab === 'personal'
      ? 'home.skillsEmptyPersonal'
      : 'home.skillsEmptyExplore'

  // #542: same call as home 创建技能; the canvas handoff sets chip / focus / chat-only full screen
  const createConversational = () => newProject({ createSkill: '1' })

  const onFav = (id: string) => setFavs(toggleFavourite(id))

  const runSkill = running ? skills.find((s) => s.id === running.id) : undefined
  const runDialog = runSkill && (
    <SkillRunDialog skill={runSkill} presetId={running?.preset} onClose={() => setRunning(null)} />
  )

  return (
    <div className="ca-skillspage" data-testid="skills-page">
      {/* #583 — chrome (title/tabs/chips) pinned; list scrolls in .ca-skills__scroll (gold header lock). */}
      <div className="ca-skills__chrome" data-testid="skills-chrome">
        <div className="ca-skills__head">
          <h1>{t('home.skills')}</h1>
          <div className="ca-skills__headacts">
            <div className="ca-skills__createwrap" ref={menuRef}>
              <button type="button" className="ca-skills__create" data-testid="skills-create" onClick={createConversational}>
                {t('home.skillsCreate')}
              </button>
              <button
                type="button"
                className="ca-skills__create ca-skills__createmore"
                data-testid="skills-create-menu"
                aria-haspopup="menu"
                aria-expanded={menu}
                title={t('skillsImport.title')}
                onClick={() => setMenu(!menu)}
              >
                <span className="ca-icon">{Icons.chevron}</span>
              </button>
              {menu && (
                <div className="ca-menu ca-skills__createmenu" role="menu">
                  <button type="button" role="menuitem" className="ca-menu__item" data-testid="skills-import" onClick={() => { setMenu(false); setImporting(true) }}>
                    <span className="ca-icon">{Icons.upload}</span>{t('skillsImport.menu')}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="ca-skills__tabs" data-testid="skills-tabs">
          <div className="ca-skills__tablist" role="tablist">
            {([
              ['explore', 'home.skillsExplore'],
              ['favourites', 'home.skillsFavourites'],
              ['personal', 'home.skillsPersonal'],
            ] as const).map(([id, key]) => (
              <button
                key={id}
                type="button"
                role="tab"
                className="ca-skills__tab"
                aria-selected={tab === id}
                data-on={tab === id || undefined}
                data-testid={`skills-tab-${id}`}
                onClick={() => setTab(id)}
              >
                {t(key)}
              </button>
            ))}
          </div>
          <div className="ca-skills__tabacts">
            <button
              type="button"
              className="ca-skills__iconbtn"
              data-testid="skills-search"
              title={t('composer.manageSkills')}
              onClick={() => skillsOpenAtom.set(true)}
            >
              <span className="ca-icon">{Icons.search}</span>
            </button>
          </div>
        </div>

        {tab === 'explore' && (
          <div className="ca-skills__chips" data-testid="skills-chips">
            {chips.map((c) => (
              <button
                key={c}
                type="button"
                className="ca-skills__chip"
                data-on={chip === c || undefined}
                data-testid={`skills-chip-${c}`}
                onClick={() => setChip(c)}
              >
                {t(CHIP_LABEL[c])}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="ca-skills__scroll" data-testid="skills-scroll">
        {tab === 'personal' ? (
          <div className="ca-skills__personal" data-testid="skills-personal">
            <section className="ca-skills__group" data-testid="skills-group-yours">
              <h2 className="ca-skills__grouptitle">{t('home.skillsCreatedByYou')}</h2>
              {yours.length === 0
                ? <div className="ca-skills__empty" data-testid="skills-empty-yours">{t('home.skillsEmptyPersonal')}</div>
                : (
                  <div className="ca-swall ca-swall--rows" data-testid="skills-wall-yours">
                    {yours.map((s) => (
                      <SkillWallCard key={s.id} skill={s} fav={favs.includes(s.id)} onFav={() => onFav(s.id)}
                        usage={usageMap[s.id] ?? 0} onTry={() => tryCard(s)} layout="row" />
                    ))}
                  </div>
                )}
            </section>
            <section className="ca-skills__group" data-testid="skills-group-loomi">
              <h2 className="ca-skills__grouptitle">{t('home.skillsCreatedByLoomi')}</h2>
              {loomi.length === 0
                ? <div className="ca-skills__empty ca-skills__empty--loomi" data-testid="skills-empty-loomi">{t('home.skillsEmptyLoomi')}</div>
                : (
                  <div className="ca-swall ca-swall--rows" data-testid="skills-wall-loomi">
                    {loomi.map((s) => (
                      <SkillWallCard key={s.id} skill={s} fav={favs.includes(s.id)} onFav={() => onFav(s.id)}
                        usage={usageMap[s.id] ?? 0} onTry={() => tryCard(s)} layout="row" />
                    ))}
                  </div>
                )}
            </section>
            <div className="ca-skills__fallback">
              <button type="button" className="ca-landing__link" onClick={() => skillsOpenAtom.set(true)}>
                {t('composer.manageSkills')} · {t('composer.skillCreatorForm')}
              </button>
            </div>
          </div>
        ) : (
          <>
            {wall.length === 0 && <div className="ca-skills__empty" data-testid="skills-empty">{t(emptyKey)}</div>}
            <div className="ca-swall" data-testid="skills-wall">
              {wall.map((s) => (
                <SkillWallCard
                  key={s.id}
                  skill={s}
                  fav={favs.includes(s.id)}
                  onFav={() => onFav(s.id)}
                  usage={usageMap[s.id] ?? 0}
                  onTry={() => tryCard(s)}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {runDialog}
      {importing && (
        <SkillImportDialog
          onClose={() => setImporting(false)}
          onImported={(skill, skipped) => {
            // #463 product ruling: go straight to the new skill's detail (duplicates land on -2/-3); skipped files get one toast.
            // #494-2 ruling 3: keep main — land on the #484 edit form (not a new detail page).
            setImporting(false)
            setTab('personal')
            const landing = importLanding(skill, skipped)
            openSkillEditor(landing.id)
            if (landing.skipped) showMemoryToast(landing.skipped, 'info')
            void loadSkills().then(setSkills)
          }}
        />
      )}
    </div>
  )
}
