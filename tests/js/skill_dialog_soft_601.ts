// #601 harness: filmstripIndexLabel pads 01…10 (pure skills.ts, no dialog SSR)
import { filmstripIndexLabel } from '../../src/skills'

const samples = [1, 2, 9, 10, 11].map(filmstripIndexLabel)
console.log(samples.join(','))
