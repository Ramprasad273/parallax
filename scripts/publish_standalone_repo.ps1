# One-command release helper to push Parallax to a new GitHub repository
param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubRepoUrl
)

Write-Host "Publishing Parallax to: $GitHubRepoUrl" -ForegroundColor Cyan
git remote remove origin 2>$null
git remote add origin $GitHubRepoUrl
git branch -M main
git push -u origin main

Write-Host "Published successfully to $GitHubRepoUrl!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Tag a release: git tag v1.0.0 && git push origin v1.0.0"
Write-Host "2. Build PyPI wheel: uv build"
Write-Host "3. Publish to PyPI: twine upload dist/*"
