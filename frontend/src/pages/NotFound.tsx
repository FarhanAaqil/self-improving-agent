import { Link } from 'react-router-dom'
import { EmptyState } from '../components/ui'

export default function NotFound() {
  return (
    <EmptyState title="No page here" action={<Link to="/" className="btn-primary">back to the workbench</Link>}>
      That address isn't in the ledger.
    </EmptyState>
  )
}
