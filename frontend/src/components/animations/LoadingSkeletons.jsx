import React from 'react'

function SkeletonLine({ width = '100%' }) {
  return <span className="content-skeleton-line" style={{ width }} />
}

export function SummarySkeleton() {
  return (
    <div className="skeleton-summary" aria-hidden="true">
      <SkeletonLine width="72%" />
      <SkeletonLine />
      <SkeletonLine width="86%" />
    </div>
  )
}

export function FlashcardSkeleton() {
  return (
    <div className="skeleton-flashcard" aria-hidden="true">
      <SkeletonLine width="24%" />
      <SkeletonLine width="70%" />
      <SkeletonLine width="44%" />
    </div>
  )
}

export function QuizSkeleton() {
  return (
    <div className="skeleton-quiz" aria-hidden="true">
      <SkeletonLine width="78%" />
      {[0, 1, 2].map((item) => <SkeletonLine key={item} />)}
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="skeleton-dashboard" aria-hidden="true">
      <div className="skeleton-dashboard-metrics">
        {[0, 1, 2].map((item) => <SkeletonLine key={item} />)}
      </div>
      <SummarySkeleton />
    </div>
  )
}

export function StudySetSkeleton() {
  return (
    <div className="study-set-skeleton" aria-hidden="true">
      <SummarySkeleton />
      <FlashcardSkeleton />
      <QuizSkeleton />
    </div>
  )
}
