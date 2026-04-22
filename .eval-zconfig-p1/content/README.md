# Documentation

## Overview

This directory contains comprehensive technical documentation for the zconfig project, including architecture designs, development guides, and implementation specifications.

## Structure

### [`architecture/`](architecture/)

Architecture documentation describing the design and structure of the zconfig system:

- **[`architecture.md`](architecture/architecture.md)** - Overall system architecture, core concepts, and workflow
- **[`cics/`](architecture/cics/)** - CICS-specific architecture documents
  - Resource builder design
  - CMCI integration
  - DCB support
  - Exec parameters
  - Extra DDs handling
  - Unix file mechanisms
  - CSD update design
  - Caching inputs
- **[`framework/`](architecture/framework/)** - Framework design documents
  - CLI arguments
  - Default logging redesign
  - Passing variables to config
  - State management
  - System symbols design

### [`development/`](development/)

Development guides and information for contributors:

- **[`code_base_overview.md`](development/code_base_overview.md)** - Overview of the codebase structure and organization
- **[`environment.md`](development/environment.md)** - Development environment setup instructions
- **[`testing.md`](development/testing.md)** - Testing approach, guidelines, and test structure
- **[`pipeline.md`](development/pipeline.md)** - CI/CD pipeline information

## Purpose

This documentation serves multiple audiences:

### For Developers

- **Understanding the System**: Architecture documents explain how components work together
- **Making Changes**: Design documents provide context for modifications
- **Setting Up**: Development guides help new contributors get started
- **Testing**: Testing documentation ensures quality standards

### For AI Agents

- **Context**: Provides background on design decisions and implementation approaches
- **Patterns**: Documents established patterns and conventions to follow
- **Constraints**: Explains technical constraints and requirements
- **Integration**: Shows how different components interact

### For Architects

- **Design Rationale**: Documents why certain architectural decisions were made
- **Trade-offs**: Explains considerations and alternatives evaluated
- **Future Direction**: Provides context for evolution and enhancements

## Key Documents

### Essential Reading

1. **[`architecture/architecture.md`](architecture/architecture.md)** - Start here to understand the overall system
2. **[`development/code_base_overview.md`](development/code_base_overview.md)** - Understand the code organization
3. **[`development/environment.md`](development/environment.md)** - Set up your development environment
4. **[`development/testing.md`](development/testing.md)** - Learn the testing approach

### CICS-Specific

If working on CICS functionality, review:
- [`architecture/cics/resource_builder.md`](architecture/cics/resource_builder.md) - Resource builder design
- [`architecture/cics/cics_cmci.md`](architecture/cics/cics_cmci.md) - CMCI integration
- [`architecture/cics/dcb_support.md`](architecture/cics/dcb_support.md) - DCB support design

### Framework Features

For framework-level changes:
- [`architecture/framework/state.md`](architecture/framework/state.md) - State management
- [`architecture/framework/passing_variables_to_config.md`](architecture/framework/passing_variables_to_config.md) - Variable support
- [`architecture/framework/cli_args.md`](architecture/framework/cli_args.md) - CLI argument handling

## Documentation Standards

### Creating New Documentation

When adding new documentation:

1. **Location**: Place in appropriate subdirectory (architecture/ or development/)
2. **Format**: Use Markdown (.md) format
3. **Structure**: Include clear sections with headers
4. **Links**: Use relative links to reference other documents
5. **Diagrams**: Use Mermaid for diagrams where helpful
6. **Examples**: Include code examples where applicable

### Updating Existing Documentation

When modifying code that affects documented behavior:

1. **Review**: Check if related documentation needs updates
2. **Update**: Modify documentation to reflect changes
3. **Consistency**: Ensure documentation remains consistent across files
4. **Accuracy**: Verify technical accuracy of updates

## Related Resources

- **[`/zconfig/README.md`](/zconfig/README.md)** - Main zconfig component documentation
- **[`/discoverygo/README.md`](/discoverygo/README.md)** - Discovery component documentation
- **[`/CONTRIBUTING.md`](/CONTRIBUTING.md)** - Contribution guidelines
- **[`/AGENTS.md`](/AGENTS.md)** - AI agent rules and conventions

## Navigation Tips

### Finding Information

- **Architecture Questions**: Start in [`architecture/`](architecture/)
- **Development Setup**: Check [`development/environment.md`](development/environment.md)
- **Testing Questions**: See [`development/testing.md`](development/testing.md)
- **CICS-Specific**: Look in [`architecture/cics/`](architecture/cics/)
- **Framework Features**: Check [`architecture/framework/`](architecture/framework/)

### Document Relationships

Many documents reference each other. Follow the links to understand:
- How components interact
- Why design decisions were made
- What alternatives were considered
- How to implement related features

## Maintenance

This documentation should be:
- **Kept Current**: Updated when code changes affect documented behavior
- **Accurate**: Verified against actual implementation
- **Complete**: Covering all major features and design decisions
- **Accessible**: Written for both human and AI agent readers
