export const atom = <T>(_n: string, v: T) => ({ get: () => v, set: (n: T) => { v = n } })
export const rulesText = () => ''
export const uuid = () => 'abcdef1234567890'
