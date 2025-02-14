module.exports = {
  branch: "master",
  plugins: [
    [
      "semantic-release-gitmoji",
      {
        releaseRules: {
          major: [":boom:"],
          minor: [":sparkles:"],
          patch: [":bug:", ":ambulance:", ":lock:"],
        },
        releaseNotes: {
          issueResolution: {
            template: "{baseUrl}/{owner}/{repo}/issues/{ref}",
            baseUrl: "https://github.com",
            source: "github.com",
            removeFromCommit: false,
            regex: /#\d+/g,
          },
        },
      },
    ],
    [
      "@semantic-release/changelog",
      {
        changelogFile: "CHANGELOG.md",
        changelogTitle: "# Semantic Versioning Changelog",
      },
    ],
    [
      "@semantic-release/exec",
      {
        prepareCmd: "./scripts/version ${nextRelease.version}",
        publishCmd: "./scripts/publish --build",
      },
    ],
    [
      "@semantic-release/git",
      {
        message:
          ":bookmark: ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}",
        assets: ["CHANGELOG.md", "pyproject.toml", "uv.lock"],
      },
    ],
    [
      "@semantic-release/github",
      {
        assets: [
          {
            path: "dist/**",
          },
        ],
      },
    ],
  ],
};
