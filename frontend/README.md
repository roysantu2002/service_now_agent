# AI Services Frontend

A production-ready Next.js frontend application for managing AI services including RAG, Incident Management, Log Analysis, and more. Features role-based access control (RBAC) with Admin and User roles.

## Features

### 🚀 Core Functionality
- **Role-Based Access Control (RBAC)**
  - Admin: Full access with analytics, approval workflows, detailed search
  - User: Service access limited to specific incidents and AI operations
- **AI Services Integration**
  - Incident Management with ServiceNow integration
  - RAG (Retrieval-Augmented Generation) system
  - Log Analyzer with pattern recognition
  - Advanced Analytics dashboard
- **Modern UI/UX**
  - Responsive design with Tailwind CSS
  - Dark/Light theme support
  - Professional navigation and layout
  - Interactive dashboards and charts

### 🔐 Authentication & Authorization
- NextAuth.js integration
- Secure session management
- Role-based route protection
- Demo accounts for testing

### 📊 Admin Dashboard Features
- Comprehensive system overview
- Real-time incident statistics
- Service status monitoring
- User activity analytics
- Advanced charts and graphs
- Approval workflows
- Detailed search capabilities

### 👤 User Dashboard Features
- Service-specific access
- Incident analysis and processing
- AI-powered insights
- Task completion tracking
- Recent activity history

## Technology Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Authentication**: NextAuth.js
- **State Management**: Zustand + React Query
- **UI Components**: Custom components with Radix UI patterns
- **Icons**: Heroicons
- **Charts**: Chart.js with react-chartjs-2
- **HTTP Client**: Axios
- **Theme**: next-themes

## Getting Started

### Prerequisites
- Node.js 18+ 
- npm or yarn
- Backend API running on http://localhost:8000 (or configure BACKEND_API_URL)

### Installation

1. **Clone and install dependencies**
   ```bash
   npm install
   ```

2. **Configure environment variables**
   ```bash
   cp .env.local.example .env.local
   ```
   
   Update `.env.local` with your configuration:
   ```env
   NEXTAUTH_SECRET=your-secret-key-here
   NEXTAUTH_URL=http://localhost:3000
   DATABASE_URL="file:./dev.db"
   BACKEND_API_URL=http://localhost:8000
   ```

3. **Start the development server**
   ```bash
   npm run dev
   ```

4. **Access the application**
   - Open http://localhost:3000
   - Use demo accounts to test functionality

### Demo Accounts

**Admin Account:**
- Email: `admin@aiservices.com`
- Password: `password123`
- Access: Full admin dashboard with analytics, user management, and approval workflows

**User Account:**
- Email: `user@aiservices.com`
- Password: `password123`
- Access: Service-specific functionality limited to assigned incidents

## Backend Integration

### API Endpoints

The frontend integrates with these backend endpoints:

```typescript
// Incident Management
POST   /incidents/create
PUT    /incidents/{sys_id}/update
POST   /incidents/process/{sys_id}
GET    /incidents/{sys_id}/summary
GET    /incidents/{sys_id}/details
POST   /incidents/{sys_id}/analyze
POST   /incidents/{sys_id}/compliance-filter
POST   /incidents/{sys_id}/insights
GET    /incidents/{sys_id}/history
```

### API Client Configuration

The application uses Axios with interceptors for:
- Automatic token injection
- Request/response logging
- Error handling
- Retry logic

## Project Structure

```
app/
├── api/auth/[...nextauth]/    # NextAuth configuration
├── auth/signin/               # Authentication pages
├── dashboard/                 # Role-based dashboards
├── incidents/                 # Incident management
├── services/                  # AI services pages
├── globals.css               # Global styles
└── layout.tsx                # Root layout

components/
├── dashboard/                # Dashboard components
│   ├── admin-dashboard.tsx
│   └── user-dashboard.tsx
├── incidents/                # Incident management components
│   ├── incident-manager.tsx
│   ├── incident-details.tsx
│   └── create-incident-form.tsx
├── layout/                   # Layout components
│   ├── navigation.tsx
│   ├── hero.tsx
│   ├── services.tsx
│   └── footer.tsx
├── providers/                # Context providers
└── ui/                       # Reusable UI components

lib/
├── api-client.ts            # Axios configuration
├── services/                # API service functions
└── utils.ts                 # Utility functions

types/
└── index.ts                 # TypeScript type definitions
```

## Key Features

### 🔒 Role-Based Access Control

```typescript
// Admin-only features
if (isAdmin) {
  // Show advanced analytics
  // Enable user management
  // Display approval workflows
}

// User-specific access
if (isUser) {
  // Show assigned incidents only
  // Limit service access
  // Hide sensitive data
}
```

### 🤖 AI Service Integration

```typescript
// Incident processing with AI
const processIncident = async (sysId: string) => {
  const result = await incidentService.processIncident(sysId)
  // Returns AI analysis, compliance info, and processing time
}

// AI-powered analysis
const analyzeIncident = async (sysId: string, type: string) => {
  const analysis = await incidentService.analyzeIncident(sysId, type)
  // Returns insights, recommendations, and similar incidents
}
```

### 📊 Dashboard Analytics

- Real-time incident statistics
- Service performance metrics
- User activity tracking
- Historical trend analysis
- Predictive insights

### 🎨 Theming & Responsive Design

- Dark/Light theme toggle
- Mobile-first responsive design
- Modern glassmorphism effects
- Smooth animations and transitions
- Accessibility-compliant components

## Development

### Available Scripts

```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run start        # Start production server
npm run lint         # Run ESLint
npm run type-check   # Run TypeScript checks
```

### Code Quality

- TypeScript for type safety
- ESLint for code linting
- Prettier for code formatting
- Consistent component patterns
- Error boundary implementation

## Production Deployment

### Environment Configuration

```env
# Production environment variables
NEXTAUTH_SECRET=production-secret-key
NEXTAUTH_URL=https://your-domain.com
BACKEND_API_URL=https://api.your-domain.com
DATABASE_URL=your-production-db-url
```

### Build and Deploy

```bash
# Build the application
npm run build

# Start production server
npm run start
```

### Performance Optimizations

- Next.js App Router for optimal loading
- Image optimization with next/image
- Code splitting and lazy loading
- React Query for efficient data fetching
- Memoization for expensive computations

## Security Features

- Secure authentication with NextAuth.js
- CSRF protection
- XSS prevention
- Role-based authorization
- Secure API communication
- Input validation and sanitization

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Email: support@aiservices.com
- Documentation: [Link to docs]
- Issue Tracker: [GitHub Issues]

---

**Built with ❤️ using Next.js and modern web technologies**