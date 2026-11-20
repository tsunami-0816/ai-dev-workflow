// 后端契约类型（来源：06.5_契约/openapi.json + 5A 接口实测）

export interface PackageVO {
  id: number
  title: string
  price: number
  coverUrl: string | null
  tags: string[]
  summary: string | null
  status: number
}

export interface PackagePage {
  list: PackageVO[]
  total: number
  page: number
  size: number
}

export interface LoginData {
  token: string
  expiresIn: number
  userId: number
  nickname: string | null
}

export interface BookingItem {
  id: number
  packageId: number
  packageTitle: string
  bookDate: string
  slot: string
  contactMasked: string
  status: number
  statusText: string
  createdAt: string
}

export interface BookingPage {
  list: BookingItem[]
  total: number
  page: number
  size: number
}

export interface BookingCreateData {
  bookingId: number
  status: number
  duplicated: boolean
}

export interface BookingInput {
  packageId: number
  bookDate: string
  slot: string
  contact: string
  remark?: string
}

export interface OpenidData {
  openid: string
  unionid: string | null
  isNewSession: boolean
}
