'use strict';
// Prints the current skill-registry digest of the ECC tree given as argv[2].
const path = require('node:path');
const repoRoot = path.resolve(process.argv[2]);
const { loadContextRegistry } = require(path.join(repoRoot, 'scripts/lib/context-pack-registry'));
process.stdout.write(loadContextRegistry({ repoRoot }).registryDigest + '\n');
