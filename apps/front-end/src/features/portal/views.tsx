'use client';

import { useAuth } from '@/components/auth-provider';
import { EmptyState } from '@/components/ui';
import { SectionDetailView as AdminSectionDetailView, SectionIndexView as AdminSectionIndexView } from '@/features/admin/views';
import { WorkspaceSectionDetailView, WorkspaceSectionIndexView } from '@/features/workspace/views';

export function PortalSectionIndexView({ section }: { section: string }) {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  if (user.role === 'admin') {
    if (section === 'assistant') return <WorkspaceSectionIndexView section="assistant" />;
    return <AdminSectionIndexView section={section} />;
  }

  if (user.role === 'internal_user') {
    return <WorkspaceSectionIndexView section={section} />;
  }

  if (user.role === 'user') {
    if (section === 'assistant') return <WorkspaceSectionIndexView section="assistant" />;
    return <EmptyState title="Assistant only" description="Your current role has access to the grounded chat assistant only." />;
  }

  return <EmptyState title="Role unavailable" description="This account does not have a configured portal workspace." />;
}

export function PortalSectionDetailView({ section, id }: { section: string; id: string }) {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  if (user.role === 'admin') {
    return <AdminSectionDetailView section={section} id={id} />;
  }

  return <WorkspaceSectionDetailView />;
}
