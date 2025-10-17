import NextAuth, { type DefaultSession, type User, type Session } from 'next-auth'
import { type JWT } from 'next-auth/jwt'
import CredentialsProvider from 'next-auth/providers/credentials'
import bcrypt from 'bcryptjs'

declare module 'next-auth' {
  interface Session {
    user: {
      id: string
      role: 'USER' | 'ADMIN'
    } & DefaultSession['user']
  }
  
  interface User {
    id: string
    role: 'USER' | 'ADMIN'
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    role: 'USER' | 'ADMIN'
  }
}

// Mock user database - in production, use real database
const users = [
  {
    id: '1',
    email: 'admin@aiservices.com',
    password: '$2a$12$7n3v14dLb1hUhl6wM.bgpeKQIWGjnxNWPQNzs8Xe.FauSKq7kgxA6', // password123
    name: 'Admin User',
    role: 'ADMIN' as const,
  },
  {
    id: '2',
    email: 'user@aiservices.com',
    password: '$2a$12$7n3v14dLb1hUhl6wM.bgpeKQIWGjnxNWPQNzs8Xe.FauSKq7kgxA6', // password123
    name: 'Regular User',
    role: 'USER' as const,
  },
]

const authOptions = {
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null
        }

        const user = users.find(u => u.email === credentials.email)
        if (!user) {
          return null
        }

        const isPasswordValid = await bcrypt.compare(credentials.password, user.password)
        if (!isPasswordValid) {
          return null
        }

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
        }
      }
    })
  ],
  callbacks: {
    async jwt({ token, user }: { token: JWT; user: User | null }) {
      if (user) {
        token.role = user.role
      }
      return token
    },
    async session({ session, token }: { session: Session; token: JWT }) {
      if (token) {
        session.user.id = token.sub!
        session.user.role = token.role
      }
      return session
    },
  },
  pages: {
    signIn: '/auth/signin',
  },
  session: {
    strategy: 'jwt' as const,
  },
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST, authOptions }