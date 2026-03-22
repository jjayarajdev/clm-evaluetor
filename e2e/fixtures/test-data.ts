/**
 * Test Data for E2E Tests
 *
 * Contains test users, contracts, and other data for testing against AWS.
 * These should match the seeded data in the database.
 */

// Test Users (from seed_data.py)
export const testUsers = {
  admin: {
    username: 'admin',
    password: 'admin123',
    role: 'admin',
    tenant: 'Acme Corp',
  },
  legal: {
    username: 'legal',
    password: 'legal123',
    role: 'legal',
    tenant: 'Acme Corp',
  },
  superAdmin: {
    username: 'superadmin',
    password: 'admin123',
    role: 'super_admin',
    tenant: null,
  },
  techstartAdmin: {
    username: 'techstart_admin',
    password: 'admin123',
    role: 'admin',
    tenant: 'TechStart',
  },
  legalcoAdmin: {
    username: 'legalco_admin',
    password: 'admin123',
    role: 'admin',
    tenant: 'LegalCo',
  },
}

// Test Tenants
export const testTenants = {
  acme: {
    name: 'Acme Corp',
    slug: 'acme',
  },
  techstart: {
    name: 'TechStart',
    slug: 'techstart',
  },
  legalco: {
    name: 'LegalCo',
    slug: 'legalco',
  },
}

// Sample contract data for upload tests
export const sampleContracts = {
  msa: {
    filename: 'Master_Service_Agreement.pdf',
    type: 'master_service_agreement',
    counterparty: 'Test Vendor Inc',
  },
  nda: {
    filename: 'NDA_Template.pdf',
    type: 'nda',
    counterparty: 'Partner Corp',
  },
  employment: {
    filename: 'Employment_Contract.pdf',
    type: 'employment',
    counterparty: 'John Doe',
  },
}

// External user test data
export const externalUsers = {
  vendor: {
    email: 'vendor@testcompany.com',
    fullName: 'Vendor Contact',
    companyName: 'Test Vendor Inc',
    title: 'Contract Manager',
  },
  partner: {
    email: 'partner@external.com',
    fullName: 'Partner Representative',
    companyName: 'Partner Corp',
    title: 'Legal Counsel',
  },
}

// Business unit test data
export const businessUnits = {
  legal: {
    name: 'Legal Department',
    code: 'LEGAL',
  },
  procurement: {
    name: 'Procurement',
    code: 'PROC',
  },
  sales: {
    name: 'Sales',
    code: 'SALES',
  },
}

// API endpoints
export const endpoints = {
  auth: {
    login: '/api/auth/login',
    logout: '/api/auth/logout',
    me: '/api/auth/me',
  },
  contracts: {
    list: '/api/contracts',
    upload: '/api/contracts/upload',
    detail: (id: string) => `/api/contracts/${id}`,
    share: (id: string) => `/api/contracts/${id}/share`,
    shares: (id: string) => `/api/contracts/${id}/shares`,
  },
  businessUnits: {
    list: '/api/business-units',
    create: '/api/business-units',
    detail: (id: string) => `/api/business-units/${id}`,
  },
  externalUsers: {
    list: '/api/external-users',
    create: '/api/external-users',
    detail: (id: string) => `/api/external-users/${id}`,
  },
  dashboard: {
    legal: '/api/dashboard/legal',
    procurement: '/api/dashboard/procurement',
    admin: '/api/dashboard/admin',
  },
  query: '/api/query',
  users: '/api/users',
  tenants: '/api/tenants',
}

// Page URLs
export const pages = {
  login: '/login',
  dashboard: '/dashboard',
  contracts: '/contracts',
  contractDetail: (id: string) => `/contracts/${id}`,
  upload: '/upload',
  query: '/query',
  users: '/users',
  settings: '/settings',
  admin: {
    businessUnits: '/admin/business-units',
    externalUsers: '/admin/external-users',
    slaConfig: '/admin/sla-config',
    scheduler: '/admin/scheduler',
  },
  superAdmin: {
    dashboard: '/super-admin',
    tenants: '/super-admin/tenants',
    users: '/super-admin/users',
  },
  external: {
    contract: (token: string) => `/external/contracts/${token}`,
  },
}
