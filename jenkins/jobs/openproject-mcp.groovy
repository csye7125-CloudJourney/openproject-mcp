// Job DSL for the openproject-mcp multibranch pipeline.
// Picks up the Jenkinsfile at the repo root.

multibranchPipelineJob('openproject-mcp') {
    displayName('openproject-mcp')
    description('Build, test, scan and push the openproject-mcp container image.')

    branchSources {
        github {
            id('openproject-mcp')
            // TODO: set the real org/repo once the github remote is wired up
            repoOwner('t3ja')
            repository('openproject-mcp')
            // public repo for now, no creds
        }
    }

    factory {
        workflowBranchProjectFactory {
            scriptPath('Jenkinsfile')
        }
    }

    orphanedItemStrategy {
        discardOldItems {
            numToKeep(20)
        }
    }

    triggers {
        periodicFolderTrigger {
            interval('1d')
        }
    }
}
