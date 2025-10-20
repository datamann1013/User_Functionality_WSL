# GitHub Copilot Instructions for RuneCore Ecosystem

## 🎯 Project Context
The RuneCore Ecosystem is a comprehensive AI service platform with security-first development practices, enterprise-grade CI/CD pipeline, and distributed architecture.

## 🔧 Code Standards & Practices

### Security Requirements
- **Never use bare `except:` statements** - Always specify exception types
- **Validate all user inputs** before processing
- **Use environment variables** for sensitive configuration
- **Implement proper authentication** for all API endpoints
- **Sanitize log outputs** to prevent information leakage

### Architecture Patterns
- **Microservices**: Each component (ai_service, ErrorLogger, hidden_toolbar) is independent
- **Docker containerization**: All services must be containerizable
- **API-first design**: RESTful APIs with proper error handling
- **Event-driven logging**: Centralized error logging through ErrorLogger service

### Code Quality Standards
- **Python**: Follow PEP 8, use type hints, minimum 85% test coverage
- **JavaScript/TypeScript**: Use ESLint with security plugins, Prettier formatting
- **Error Handling**: Specific exception types, meaningful error messages
- **Documentation**: Comprehensive docstrings and README files

### CI/CD Pipeline Integration
- **All code changes** must pass security scanning (CodeQL, Semgrep, TruffleHog)
- **Performance regression** detection with 10% threshold
- **Cross-platform testing** on Ubuntu, Windows-WSL, Kali, Arch, Debian
- **Artifact management** with SHA256 checksums and retention policies

## 🚫 Anti-Patterns to Avoid

### Docker & Build Issues
- **Never use `../` in Docker COPY commands** - Use full paths from build context root
- **Avoid relative imports** in production code - Use absolute imports
- **Don't hardcode ports** - Use environment variables with sensible defaults

### Security Anti-Patterns
- **No hardcoded credentials** or API keys in source code
- **No bare except clauses** - Always catch specific exceptions
- **No direct database queries** without parameterization
- **No logging of sensitive data** (passwords, tokens, PII)

### Performance Anti-Patterns
- **Avoid synchronous blocking calls** in async contexts
- **Don't ignore memory usage** in long-running processes
- **No infinite loops** without proper exit conditions
- **Avoid nested loops** with high complexity

## 📝 Code Review Checklist

### Security Review
- [ ] No hardcoded secrets or credentials
- [ ] Proper input validation and sanitization
- [ ] Authentication and authorization implemented
- [ ] Error messages don't leak sensitive information
- [ ] Dependencies are up-to-date and scanned for vulnerabilities

### Architecture Review
- [ ] Follows microservices patterns
- [ ] Proper separation of concerns
- [ ] Database migrations are reversible
- [ ] API endpoints follow RESTful conventions
- [ ] Logging is centralized through ErrorLogger

### Performance Review
- [ ] No obvious performance bottlenecks
- [ ] Memory usage is reasonable
- [ ] Database queries are optimized
- [ ] Caching is implemented where appropriate
- [ ] Async operations are used for I/O

### Quality Review
- [ ] Code follows established patterns
- [ ] Tests provide adequate coverage (≥85%)
- [ ] Documentation is updated
- [ ] Error handling is comprehensive
- [ ] Code is readable and maintainable

## 🔍 Component-Specific Guidelines

### AI Service (projects/ai_service/)
- **Port**: Default 5000, configurable via `PORT` environment variable
- **Authentication**: JWT-based with configurable secret
- **Model Management**: Support for multiple AI model backends
- **Rate Limiting**: Implement to prevent abuse
- **Health Checks**: Essential for container orchestration

### ErrorLogger (projects/ErrorLogger/)
- **Port**: Default 5001, configurable via `ERRORLOGGER_PORT`
- **Log Retention**: Configurable retention policies
- **PII Sanitization**: Automatic removal of sensitive data
- **Structured Logging**: JSON format with consistent schema
- **Performance**: Low-latency logging to prevent application blocking

### Hidden Toolbar (projects/hidden_toolbar/)
- **System Integration**: Safe interaction with OS APIs
- **Privilege Management**: Minimal required permissions
- **UI Responsiveness**: Non-blocking user interface
- **Resource Usage**: Lightweight system footprint
- **Cross-Platform**: Support for multiple Linux distributions

## 🛠️ Development Workflow

### Branch Strategy
- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/***: Individual feature development
- **hotfix/***: Critical production fixes

### Pull Request Requirements
- [ ] All CI/CD checks pass
- [ ] Code review approved by maintainer
- [ ] Documentation updated if needed
- [ ] Performance benchmarks within acceptable range
- [ ] Security scan results reviewed

### Testing Strategy
- **Unit Tests**: Minimum 85% coverage
- **Integration Tests**: Component interaction validation
- **Security Tests**: Vulnerability scanning and penetration testing
- **Performance Tests**: Regression detection and benchmarking
- **End-to-End Tests**: Complete workflow validation

## 📊 Monitoring & Observability

### Metrics Collection
- **Performance**: Memory usage, CPU utilization, response times
- **Security**: Failed authentication attempts, suspicious activities
- **Business**: API usage patterns, error rates, user interactions
- **Infrastructure**: Container health, resource utilization

### Alerting Thresholds
- **Critical**: Security breaches, service outages
- **Warning**: Performance degradation >10%, high error rates
- **Info**: Deployment notifications, configuration changes

## 🚀 Deployment Considerations

### Environment Configuration
- **Development**: Local development with Docker Compose
- **Staging**: Container orchestration with full security scanning
- **Production**: Multi-region deployment with high availability
- **Disaster Recovery**: Automated backups and rollback procedures

### Scaling Patterns
- **Horizontal Scaling**: Stateless service design
- **Load Balancing**: Distribute traffic across instances
- **Database Sharding**: Handle large-scale data requirements
- **Caching Layers**: Redis for session management and caching

---

**Remember**: Security first, performance matters, quality is non-negotiable.
**Last Updated**: October 2025
**Version**: 1.0.0
