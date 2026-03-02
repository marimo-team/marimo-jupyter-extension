/**
 * @type {import('eslint').Linter.Config}
 */
module.exports = {
  root: true,
  extends: [
    'eslint:recommended',
    // This ruleset is meant to be used after extending eslint:recommended.
    // It disables core ESLint rules that are already checked by the TypeScript compiler.
    'plugin:@typescript-eslint/eslint-recommended',
    // TS ESLint
    'plugin:@typescript-eslint/recommended-type-checked',
    'plugin:@typescript-eslint/stylistic-type-checked',
    // React
    'plugin:react-hooks/recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    // This removes rules that conflict with prettier/biomejs.
    'prettier',
  ],
  settings: {
    react: {
      version: 'detect',
    },
  },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    project: require.resolve('./tsconfig.json'),
  },
  plugins: ['@typescript-eslint'],
  rules: {
    // Rules disabled because they have Biome equivalents
    curly: 'off', // → useBlockStatements in Biome
    'default-param-last': 'off', // → useDefaultParameterLast in Biome
    eqeqeq: 'off', // → noDoubleEquals in Biome
    'no-console': 'off', // → noConsole in Biome
    'no-debugger': 'off', // → noDebugger in Biome
    'no-empty': 'off', // → noEmptyBlockStatements in Biome
    'no-inner-declarations': 'off', // → noInnerDeclarations in Biome
    'no-useless-constructor': 'off', // → noUselessConstructor in Biome
    'no-control-regex': 'off', // → noControlRegex in Biome
    'no-var': 'off', // → noVar in Biome
    'prefer-const': 'off', // → useConst in Biome
    'prefer-template': 'off', // → useTemplate in Biome

    // These rules don't require type information and have autofixes
    '@typescript-eslint/consistent-generic-constructors': 'error',
    '@typescript-eslint/consistent-type-definitions': 'error',
    '@typescript-eslint/no-confusing-non-null-assertion': 'error',
    '@typescript-eslint/no-dynamic-delete': 'error',

    // Turn off recommended we don't want
    'react/prop-types': 'off',
    'react/no-unescaped-entities': 'off',
    'react/jsx-no-target-blank': 'off',
    '@typescript-eslint/no-unnecessary-condition': 'off',
    '@typescript-eslint/use-unknown-in-catch-callback-variable': 'off',
    '@typescript-eslint/no-confusing-void-expression': [
      'error',
      { ignoreArrowShorthand: true },
    ],
    '@typescript-eslint/prefer-nullish-coalescing': 'off',
    '@typescript-eslint/no-unused-vars': 'off', // Handled by Biome noUnusedImports
    '@typescript-eslint/consistent-indexed-object-style': 'off',
    '@typescript-eslint/require-await': 'off',
    '@typescript-eslint/restrict-template-expressions': 'off',
    '@typescript-eslint/no-floating-promises': 'off', // JupyterLab async patterns
    '@typescript-eslint/no-misused-promises': 'off', // JupyterLab async patterns
  },
  ignorePatterns: ['lib/**', 'node_modules/**', '*.js', '*.cjs', '*.test.ts'],
};
